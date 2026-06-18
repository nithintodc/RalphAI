"""
DoorDash Merchant Portal automation using the browser-use framework.
Runs the full workflow: login, financial report, marketing report, download(s), and campaign creation.
Returns paths to downloaded report file(s) for use by analysis_agent and marketing_agent.
"""

import asyncio
import logging
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, Tuple

# Timeouts (seconds) for each browser-use agent phase
AGENT_REPORTS_TIMEOUT = 900   # 15 min: login + create 2 reports + download both
AGENT_SINGLE_REPORT_TIMEOUT = 600  # 10 min per report type (Data Run sequential mode)
AGENT_LOGIN_TIMEOUT = 180     # 3 min: re-login after browser restart
AGENT_RESET_TIMEOUT = 90      # 1.5 min: navigate to Marketing page between campaigns
AGENT_CAMPAIGN_TIMEOUT = 720  # 12 min: create one campaign end-to-end (increased from 540 to handle many-slot campaigns)

# Campaigns per browser session before restart; override via env for tuning
MAX_CAMPAIGNS_PER_SESSION = int(os.getenv("MAX_CAMPAIGNS_PER_SESSION", "5"))

# Shared between reporting Phase 2 and Ralph Offers/Ads (_run_campaign_items).
_NAV_TO_MARKETING_TASK = (
    "Go to this URL: https://merchant-portal.doordash.com/merchant/marketing "
    "WAIT UNTIL the page has fully loaded. "
    "If any modal, popup, dialog, or overlay is visible, close it by clicking 'X', 'Close', 'Cancel', or pressing Escape. "
    "Confirm you see the Marketing page with campaign-related content. Use the done action to finish."
)
_MARKETING_RESET_FALLBACK_TASK = (
    "IMPORTANT: Before navigating, check if any modal, popup, dialog, or overlay is currently visible on the page. "
    "If so, close it by clicking 'X', 'Close', 'Cancel', or pressing Escape. "
    "Then navigate to the DoorDash Merchant Portal dashboard. "
    "In the LEFT SIDEBAR, click 'Marketing'. "
    "WAIT UNTIL the Marketing page has fully loaded (you see campaign-related content, not a loading spinner). "
    "If the page shows an error or doesn't load, try clicking 'Marketing' in the sidebar again. "
    "Confirm you see the Marketing page. Use the done action to finish."
)
_PAGE_HEALTH_CHECK_TASK = (
    "Check if the DoorDash Merchant Portal page is loaded and interactive. "
    "Look for sidebar navigation, page content, or any visible UI elements. "
    "If the page is blank, showing only a spinner, or unresponsive, say 'PAGE_BLANK'. "
    "Otherwise say 'PAGE_OK'. Use the done action."
)

from agents.combined_report_agent import (
    append_campaign_mappings_to_workbook,
    copy_campaign_mappings_from_previous,
    read_campaign_combos_from_mappings,
    read_campaign_mapping_statuses,
    update_campaign_mapping_status,
)
from agents.slack_agent import push_to_slack
from shared import ralph_slack_messages as slack_msg

logger = logging.getLogger(__name__)


def _build_campaign_tools():
    """
    Build a Tools instance with a custom 'set_schedule_grid' action.
    Uses CDP Input.dispatchMouseEvent (native browser input pipeline) to click grid cells,
    which reliably triggers React's synthetic event system — unlike JS dispatchEvent which doesn't.
    """
    from browser_use import Tools
    from browser_use.agent.views import ActionResult

    tools = Tools()

    _GRID_ROW_NAMES = ["Overnight", "Breakfast", "Lunch", "Afternoon", "Dinner", "Late night"]
    _GRID_COL_NAMES = ["Mon", "Tue", "Wed", "Thur", "Fri", "Sat", "Sun"]

    def _tag_label(tag: int) -> str:
        """Human-readable label for a tag number, e.g. 8 → 'Breakfast/Mon'."""
        row_idx = (tag - 1) // 7
        col_idx = (tag - 1) % 7
        return f"{_GRID_ROW_NAMES[row_idx]}/{_GRID_COL_NAMES[col_idx]}"

    @tools.action(
        description=(
            "Set the DoorDash campaign schedule grid to exactly the desired state. "
            "Pass 'wanted_tags' as a comma-separated string of tag numbers (1-42) that should be CHECKED. "
            "Grid layout: 6 rows (Overnight, Breakfast, Lunch, Afternoon, Dinner, Late night) x 7 cols (Mon-Sun). "
            "Tag 1 = Mon/Overnight, Tag 2 = Tue/Overnight, ..., Tag 7 = Sun/Overnight, "
            "Tag 8 = Mon/Breakfast, ..., Tag 42 = Sun/Late night. "
            "This action detects current cell states and only toggles cells that need to change, then clicks Save. "
            "Example: wanted_tags='1,2,3,8,9' means check Mon/Tue/Wed Overnight + Mon/Tue Breakfast. "
            "IMPORTANT: Call this ONCE after the custom schedule grid is visible. Do NOT manually click any grid cells."
        ),
    )
    async def set_schedule_grid(wanted_tags: str, browser_session) -> ActionResult:
        """Detect current grid state, toggle only cells that need changing, using CDP native clicks."""
        try:
            wanted = set()
            for t in wanted_tags.split(","):
                t = t.strip()
                if t and t.isdigit():
                    wanted.add(int(t))

            logger.info("set_schedule_grid CALLED: wanted_tags=%s → wanted=%s", wanted_tags, sorted(wanted))
            logger.info("set_schedule_grid: wanted cells: %s",
                        ", ".join(f"{t}({_tag_label(t)})" for t in sorted(wanted)))

            cdp_session = await browser_session.get_or_create_cdp_session()
            cdp_client = cdp_session.cdp_client
            session_id = cdp_session.session_id

            # Step 1: Find grid cells, detect their checked state, and get viewport coordinates.
            # Checked cells have a visible checkmark (SVG path with non-zero opacity / colored fill).
            # Unchecked cells have a hidden/transparent SVG.
            js_find_grid = """
(function() {
    // Find Weekdays button to anchor in the schedule modal
    var weekdaysBtn = null;
    var allBtns = document.querySelectorAll('button');
    for (var i = 0; i < allBtns.length; i++) {
        if (allBtns[i].textContent.trim() === 'Weekdays') { weekdaysBtn = allBtns[i]; break; }
    }
    if (!weekdaysBtn) return JSON.stringify({error: 'No Weekdays button found on page'});

    // Walk up to find modal container
    var container = weekdaysBtn;
    for (var up = 0; up < 12; up++) {
        container = container.parentElement;
        if (!container) break;
    }
    if (!container) return JSON.stringify({error: 'Could not find modal container'});

    // Find grid rows — divs with exactly 7 children that each contain an SVG
    var rows = [];
    var candidateRows = container.querySelectorAll('div[class*="StyledInlineChildren"]');
    for (var r = 0; r < candidateRows.length; r++) {
        var row = candidateRows[r];
        if (row.children.length === 7) {
            var allHaveSvg = true;
            for (var c = 0; c < 7; c++) {
                if (!row.children[c].querySelector('svg')) { allHaveSvg = false; break; }
            }
            if (allHaveSvg) rows.push(row);
        }
    }
    // Fallback 1: any div with 7 SVG-bearing children
    if (rows.length < 6) {
        rows = [];
        var allDivs = container.querySelectorAll('div');
        for (var d = 0; d < allDivs.length; d++) {
            var div = allDivs[d];
            if (div.children.length === 7) {
                var ok = true;
                for (var c2 = 0; c2 < 7; c2++) {
                    if (!div.children[c2].querySelector('svg')) { ok = false; break; }
                }
                if (ok) rows.push(div);
            }
        }
    }
    // Fallback 2: div with 7 children, NO SVG requirement (grid after clearing)
    if (rows.length < 6) {
        var wkRect = weekdaysBtn.getBoundingClientRect();
        var gridMinY = wkRect.bottom - 5;
        rows = [];
        var allDivs2 = container.querySelectorAll('div');
        for (var d2 = 0; d2 < allDivs2.length; d2++) {
            var dv2 = allDivs2[d2];
            if (dv2.children.length === 7) {
                var dvR = dv2.getBoundingClientRect();
                if (dvR.top >= gridMinY && dvR.height > 25 && dvR.height < 200) {
                    var childOk = true;
                    for (var c3 = 0; c3 < 7; c3++) {
                        var chR = dv2.children[c3].getBoundingClientRect();
                        if (chR.width < 15 || chR.height < 15) { childOk = false; break; }
                    }
                    if (childOk) rows.push(dv2);
                }
            }
        }
        rows.sort(function(a, b) { return a.getBoundingClientRect().top - b.getBoundingClientRect().top; });
        if (rows.length > 6) rows = rows.slice(rows.length - 6);
    }
    if (rows.length < 6) return JSON.stringify({error: 'Found ' + rows.length + ' grid rows, expected 6'});

    // Detect checked state for each cell.
    // Strategy: check background color of the cell div, or SVG checkmark visibility.
    // DoorDash selected cells have a teal/green background; unselected have white/light gray.
    function isChecked(cellDiv) {
        var style = window.getComputedStyle(cellDiv);
        var bg = style.backgroundColor;
        // Also check the first child div (sometimes the colored background is on inner div)
        var innerDiv = cellDiv.querySelector('div');
        var innerBg = innerDiv ? window.getComputedStyle(innerDiv).backgroundColor : '';

        // Check for teal/green-ish backgrounds (selected state)
        // Teal: rgb(0, 175, 169) or similar; selected cells are NOT white/transparent
        function isTealish(color) {
            if (!color || color === 'rgba(0, 0, 0, 0)' || color === 'transparent') return false;
            // Parse rgb values
            var m = color.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
            if (!m) return false;
            var r = parseInt(m[1]), g = parseInt(m[2]), b = parseInt(m[3]);
            // White or very light (unselected)
            if (r > 240 && g > 240 && b > 240) return false;
            // Near-white grays
            if (r > 220 && g > 220 && b > 220 && Math.abs(r-g) < 15 && Math.abs(g-b) < 15) return false;
            // Has significant color = selected
            return true;
        }

        if (isTealish(bg)) return true;
        if (isTealish(innerBg)) return true;

        // Fallback: check SVG path opacity
        var svg = cellDiv.querySelector('svg');
        if (svg) {
            var path = svg.querySelector('path');
            if (path) {
                var pathStyle = window.getComputedStyle(path);
                var stroke = pathStyle.stroke;
                var fill = pathStyle.fill;
                // If path has visible stroke/fill (not transparent/none)
                if (stroke && stroke !== 'none' && stroke !== 'rgba(0, 0, 0, 0)') return true;
                if (fill && fill !== 'none' && fill !== 'rgba(0, 0, 0, 0)') {
                    // Check it's not white
                    var fm = fill.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                    if (fm) {
                        var fr = parseInt(fm[1]), fg = parseInt(fm[2]), fb = parseInt(fm[3]);
                        if (fr < 240 || fg < 240 || fb < 240) return true;
                    }
                }
            }
            // Check svg visibility/opacity
            var svgStyle = window.getComputedStyle(svg);
            if (svgStyle.opacity === '0' || svgStyle.visibility === 'hidden') return false;
        }

        // Final fallback: check aria-checked or data attributes
        if (cellDiv.getAttribute('aria-checked') === 'true') return true;
        if (cellDiv.getAttribute('aria-checked') === 'false') return false;

        // Default: assume UNchecked — prevents correction loop from double-toggling
        return false;
    }

    var result = {cells: [], saveBtn: null};
    for (var ri = 0; ri < 6; ri++) {
        for (var ci = 0; ci < 7; ci++) {
            var cell = rows[ri].children[ci];
            var rect = cell.getBoundingClientRect();
            var checked = isChecked(cell);
            result.cells.push({
                tag: ri * 7 + ci + 1,
                x: Math.round(rect.left + rect.width / 2),
                y: Math.round(rect.top + rect.height / 2),
                checked: checked
            });
        }
    }

    // Find Save button
    var modalBtns = container.querySelectorAll('button');
    for (var j = 0; j < modalBtns.length; j++) {
        var btnTxt = modalBtns[j].textContent.trim();
        if (btnTxt === 'Save' || btnTxt === 'Save schedule') {
            var sRect = modalBtns[j].getBoundingClientRect();
            result.saveBtn = {x: Math.round(sRect.left + sRect.width / 2), y: Math.round(sRect.top + sRect.height / 2)};
            break;
        }
    }
    // Record initial Weekdays button y so we can measure banner-shift later
    var wRect = weekdaysBtn.getBoundingClientRect();
    result.weekdaysY = Math.round(wRect.top + wRect.height / 2);
    return JSON.stringify(result);
})()
"""
            # Get grid state + coordinates
            eval_result = await cdp_client.send.Runtime.evaluate(
                params={"expression": js_find_grid, "returnByValue": True, "awaitPromise": True},
                session_id=session_id,
            )
            if eval_result.get("exceptionDetails"):
                err = eval_result["exceptionDetails"].get("text", "Unknown JS error")
                logger.warning("set_schedule_grid JS error: %s", err)
                return ActionResult(error=f"JavaScript error finding grid: {err}")

            import json
            raw_val = eval_result.get("result", {}).get("value", "{}")
            grid_info = json.loads(raw_val) if isinstance(raw_val, str) else raw_val

            if "error" in grid_info:
                logger.warning("set_schedule_grid: %s", grid_info["error"])
                return ActionResult(error=grid_info["error"])

            cells = grid_info["cells"]  # list of {tag, x, y, checked}
            save_btn = grid_info.get("saveBtn")
            initial_weekdays_y: int = grid_info.get("weekdaysY", 0)  # for banner-shift measurement

            if len(cells) != 42:
                return ActionResult(error=f"Expected 42 cells, found {len(cells)}")

            # Log current grid state
            currently_checked = {c["tag"] for c in cells if c.get("checked")}
            currently_unchecked = {c["tag"] for c in cells if not c.get("checked")}
            logger.info("set_schedule_grid: CURRENT STATE: %d checked, %d unchecked",
                        len(currently_checked), len(currently_unchecked))
            logger.info("set_schedule_grid: currently checked tags: %s", sorted(currently_checked))
            logger.info("set_schedule_grid: currently unchecked tags: %s", sorted(currently_unchecked))

            # Determine which cells need to be TOGGLED:
            # - Cells that are checked but should NOT be → click to uncheck
            # - Cells that are unchecked but SHOULD be → click to check
            need_uncheck = currently_checked - wanted   # checked but unwanted
            need_check = wanted - currently_checked      # unchecked but wanted
            no_change = wanted & currently_checked       # already correct

            logger.info("set_schedule_grid: PLAN: %d to uncheck, %d to check, %d already correct",
                        len(need_uncheck), len(need_check), len(no_change))
            if need_uncheck:
                logger.info("set_schedule_grid: UNCHECK: %s",
                            ", ".join(f"{t}({_tag_label(t)})" for t in sorted(need_uncheck)))
            if need_check:
                logger.info("set_schedule_grid: CHECK: %s",
                            ", ".join(f"{t}({_tag_label(t)})" for t in sorted(need_check)))

            to_click = need_uncheck | need_check  # all cells that need toggling

            # Helper: click at viewport coordinates using CDP Input.dispatchMouseEvent
            async def cdp_click(x: int, y: int):
                await cdp_client.send.Input.dispatchMouseEvent(
                    params={"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1},
                    session_id=session_id,
                )
                await cdp_client.send.Input.dispatchMouseEvent(
                    params={"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1},
                    session_id=session_id,
                )
                await asyncio.sleep(0.05)  # tiny delay for React to process

            # ── CLICK STRATEGY ────────────────────────────────────────────────────────
            # Rule: if len(wanted) ≤ 21 → CLEAR-AND-SELECT
            #         Click Weekdays + Weekends to empty the grid, then CHECK each
            #         wanted cell.  Only 2 + len(wanted) clicks.
            #       if len(wanted) > 21 → UNCHECK-UNWANTED
            #         Directly UNCHECK each cell not in wanted.
            #
            # COORDINATE APPROACH — banner-shift adjustment:
            #   The initial scan captures CORRECT coordinates (all cells have SVGs,
            #   grid is stable, no banner).  After we start toggling cells, DoorDash
            #   inserts a "Run all day" recommendation banner that pushes the grid
            #   DOWN by its height (typically 50-120 px).
            #
            #   Rather than re-querying the DOM for each cell (which can find the
            #   wrong row due to ambiguous 7-child sibling matching), we:
            #     1. Record the Weekdays button y at initial scan time (no banner).
            #     2. Before each cell click, re-read the Weekdays button y.
            #     3. shift = current_weekdays_y - initial_weekdays_y
            #     4. Adjusted click = (initial_x, initial_y + shift)
            #   Since the banner pushes BOTH the Weekdays button AND grid cells down
            #   by the same amount, this single measurement corrects all coordinates.
            # ──────────────────────────────────────────────────────────────────────────

            clicked = 0
            cell_coords = {c["tag"]: (c["x"], c["y"]) for c in cells}

            # JS that returns the current Weekdays button y (to measure banner shift)
            _JS_WEEKDAYS_Y = (
                "(function(){"
                "var bs=document.querySelectorAll('button');"
                "for(var i=0;i<bs.length;i++){"
                "if(bs[i].textContent.trim()==='Weekdays'){"
                "var r=bs[i].getBoundingClientRect();"
                "return JSON.stringify({y:Math.round(r.top+r.height/2)});}}"
                "return '{}';  })()"
            )

            # JS that returns the current coords of a named button within the modal
            _JS_BTN_COORD = (
                "(function(t){"
                "var w=null,bs=document.querySelectorAll('button');"
                "for(var i=0;i<bs.length;i++){if(bs[i].textContent.trim()==='Weekdays'){w=bs[i];break;}}"
                "if(!w)return'{}';"
                "var c=w;for(var u=0;u<12;u++){c=c.parentElement;if(!c)break;}"
                "if(!c)return'{}';"
                "var tgt=null,ab=c.querySelectorAll('button');"
                "for(var i=0;i<ab.length;i++){if(ab[i].textContent.trim()===t){tgt=ab[i];break;}}"
                "if(!tgt)return'{}';"
                "var r=tgt.getBoundingClientRect();"
                "return JSON.stringify({x:Math.round(r.left+r.width/2),y:Math.round(r.top+r.height/2)});"
                "})"
            )

            async def _get_banner_shift() -> int:
                """Measure how far the banner pushed the grid down since initial scan."""
                if not initial_weekdays_y:
                    return 0
                try:
                    res = await cdp_client.send.Runtime.evaluate(
                        params={"expression": _JS_WEEKDAYS_Y, "returnByValue": True, "awaitPromise": True},
                        session_id=session_id,
                    )
                    val = res.get("result", {}).get("value", "{}")
                    curr_y = (json.loads(val) if isinstance(val, str) else val).get("y", 0)
                    if curr_y:
                        return curr_y - initial_weekdays_y
                except Exception:
                    pass
                return 0

            _JS_FIND_CELL = (
                "(function(ri,ci){"
                "var w=null,bs=document.querySelectorAll('button');"
                "for(var i=0;i<bs.length;i++){if(bs[i].textContent.trim()==='Weekdays'){w=bs[i];break;}}"
                "if(!w)return JSON.stringify({error:'no_weekdays'});"
                "var c=w;for(var u=0;u<12;u++){c=c.parentElement;if(!c)break;}"
                "if(!c)return JSON.stringify({error:'no_container'});"
                "var wRect=w.getBoundingClientRect();var minY=wRect.bottom-5;"
                "var rows=[];"
                "var cr=c.querySelectorAll('div[class*=\"StyledInlineChildren\"]');"
                "for(var r=0;r<cr.length;r++){var rw=cr[r];"
                "if(rw.children.length===7){var ok=true;"
                "for(var x=0;x<7;x++){if(!rw.children[x].querySelector('svg')){ok=false;break;}}"
                "if(ok)rows.push(rw);}}"
                "if(rows.length<6){rows=[];"
                "for(var r2=0;r2<cr.length;r2++){var rw2=cr[r2];"
                "if(rw2.children.length===7){"
                "var rr=rw2.getBoundingClientRect();"
                "if(rr.top>=minY&&rr.height>25&&rr.height<200){"
                "var co=true;"
                "for(var x2=0;x2<7;x2++){var ch=rw2.children[x2].getBoundingClientRect();"
                "if(ch.width<15||ch.height<15){co=false;break;}}"
                "if(co)rows.push(rw2);}}}}"
                "if(rows.length<6){rows=[];"
                "var ad=c.querySelectorAll('div');"
                "for(var d=0;d<ad.length;d++){var dv=ad[d];"
                "if(dv.children.length===7){"
                "var dr=dv.getBoundingClientRect();"
                "if(dr.top>=minY&&dr.height>25&&dr.height<200){"
                "var ok3=true;"
                "for(var x3=0;x3<7;x3++){var cr3=dv.children[x3].getBoundingClientRect();"
                "if(cr3.width<15||cr3.height<15){ok3=false;break;}}"
                "if(ok3)rows.push(dv);}}}}"
                "rows.sort(function(a,b){return a.getBoundingClientRect().top-b.getBoundingClientRect().top;});"
                "if(rows.length>6)rows=rows.slice(rows.length-6);"
                "if(rows.length<6)return JSON.stringify({error:'rows_'+rows.length});"
                "var cell=rows[ri].children[ci];"
                "cell.scrollIntoView({behavior:'instant',block:'nearest'});"
                "var rect=cell.getBoundingClientRect();"
                "return JSON.stringify({x:Math.round(rect.left+rect.width/2),y:Math.round(rect.top+rect.height/2)});"
                "})"
            )

            async def _click_cell(tag: int, action: str) -> bool:
                """Click a grid cell by finding it fresh in the DOM each time."""
                row_idx = (tag - 1) // 7
                col_idx = (tag - 1) % 7
                row_label = _GRID_ROW_NAMES[row_idx]
                col_name = _GRID_COL_NAMES[col_idx]
                js = _JS_FIND_CELL + f"({row_idx},{col_idx})"
                try:
                    res = await cdp_client.send.Runtime.evaluate(
                        params={"expression": js, "returnByValue": True, "awaitPromise": True},
                        session_id=session_id,
                    )
                    raw = res.get("result", {}).get("value", "{}")
                    coord = json.loads(raw) if isinstance(raw, str) else raw
                    if "error" not in coord:
                        x, y = coord.get("x", 0), coord.get("y", 0)
                        if x and y:
                            logger.info("set_schedule_grid: %s tag %d (%s/%s) at (%d,%d) [fresh]",
                                        action, tag, row_label, col_name, x, y)
                            await cdp_click(x, y)
                            return True
                    logger.debug("set_schedule_grid: fresh coord failed for tag %d: %s",
                                 tag, coord.get("error", ""))
                except Exception as e:
                    logger.debug("set_schedule_grid: fresh coord JS error for tag %d: %s", tag, e)
                # Fallback: cached coordinates + banner shift
                x, y = cell_coords.get(tag, (0, 0))
                if not (x and y):
                    logger.warning("set_schedule_grid: no coord for tag %d", tag)
                    return False
                shift = await _get_banner_shift()
                adj_y = y + shift
                logger.info("set_schedule_grid: %s tag %d (%s/%s) at (%d,%d) [cached, shift=%+d]",
                            action, tag, row_label, col_name, x, adj_y, shift)
                await cdp_click(x, adj_y)
                return True

            async def _click_modal_btn(btn_text: str) -> bool:
                """Click a button inside the schedule modal by its text label (live coords)."""
                js = _JS_BTN_COORD + "(" + json.dumps(btn_text) + ")"
                try:
                    res = await cdp_client.send.Runtime.evaluate(
                        params={"expression": js, "returnByValue": True, "awaitPromise": True},
                        session_id=session_id,
                    )
                    val = res.get("result", {}).get("value", "{}")
                    coord = json.loads(val) if isinstance(val, str) else val
                    x, y = coord.get("x", 0), coord.get("y", 0)
                    if x and y:
                        await cdp_click(x, y)
                        logger.info("set_schedule_grid: clicked '%s' button at (%d,%d)", btn_text, x, y)
                        return True
                except Exception as e:
                    logger.debug("set_schedule_grid: btn '%s' failed: %s", btn_text, e)
                logger.warning("set_schedule_grid: could not find/click '%s' button", btn_text)
                return False

            async def _settle_and_scroll_bottom() -> None:
                """Wait for the banner to fully appear, then scroll the modal to the bottom.

                After clicking Weekdays/Weekends (or the first cell toggle), DoorDash
                inserts a 'Run all day' recommendation banner that:
                  • shifts the grid downward (handled by _click_cell's shift measurement)
                  • may cause the bottom rows to overflow the modal's visible area

                Scrolling to the bottom ensures Dinner/Late night rows are fully on-screen
                before we start clicking cells.  The Weekdays-button shift reference remains
                valid because both the button and the grid cells share the same scroll container
                and move by the same offset.
                """
                await asyncio.sleep(2.0)   # let the banner render and the layout settle

                # Scroll the modal's inner scroll container all the way to the bottom
                js_scroll_bottom = (
                    "(function(){"
                    "var w=null,bs=document.querySelectorAll('button');"
                    "for(var i=0;i<bs.length;i++){if(bs[i].textContent.trim()==='Weekdays'){w=bs[i];break;}}"
                    "if(!w)return '0';"
                    "var c=w;"
                    "for(var u=0;u<12;u++){c=c.parentElement;if(!c)break;}"
                    "if(c&&c.scrollHeight>c.clientHeight){c.scrollTop=c.scrollHeight;return String(c.scrollTop);}"
                    "return '0';})()"
                )
                try:
                    res = await cdp_client.send.Runtime.evaluate(
                        params={"expression": js_scroll_bottom, "returnByValue": True, "awaitPromise": True},
                        session_id=session_id,
                    )
                    scrolled = res.get("result", {}).get("value", "0")
                    logger.info("set_schedule_grid: scrolled modal to bottom (scrollTop=%s)", scrolled)
                except Exception as scroll_err:
                    logger.debug("set_schedule_grid: scroll-to-bottom failed: %s", scroll_err)

                await asyncio.sleep(0.5)   # let scroll settle before measuring shift + clicking

            async def _refresh_grid_coords_from_dom() -> bool:
                """Re-capture cell (x,y) and weekdaysY after scroll/layout.

                _settle_and_scroll_bottom() changes the modal's scrollTop. Cached
                coordinates from the *initial* scan were taken at scrollTop≈0.
                The Weekdays-button banner-shift trick only works if Weekdays and
                every grid cell move identically in viewport space. DoorDash often
                puts Weekdays/Weekends in a sticky header or a different subtree than
                the scrolled pane — then shift under-corrects and clicks land too low,
                missing the bottom (Late night) row entirely while upper rows work.

                Refreshing coords after scroll fixes slots 36–42 without relying on
                that assumption.
                """
                nonlocal cell_coords, initial_weekdays_y
                try:
                    res = await cdp_client.send.Runtime.evaluate(
                        params={"expression": js_find_grid, "returnByValue": True, "awaitPromise": True},
                        session_id=session_id,
                    )
                    if res.get("exceptionDetails"):
                        return False
                    raw_val = res.get("result", {}).get("value", "{}")
                    fresh = json.loads(raw_val) if isinstance(raw_val, str) else raw_val
                    if "error" in fresh or len(fresh.get("cells", [])) != 42:
                        logger.warning(
                            "set_schedule_grid: coord refresh skipped: %s",
                            fresh.get("error", "not 42 cells"),
                        )
                        return False
                    cell_coords = {c["tag"]: (c["x"], c["y"]) for c in fresh["cells"]}
                    initial_weekdays_y = int(fresh.get("weekdaysY") or 0)
                    logger.info(
                        "set_schedule_grid: refreshed coordinates after scroll/layout "
                        "(weekdays_y=%s, sample tag42=%s)",
                        initial_weekdays_y,
                        cell_coords.get(42),
                    )
                    return True
                except Exception as ex:
                    logger.warning("set_schedule_grid: coord refresh failed: %s", ex)
                    return False

            # ── ALWAYS CLEAR-AND-SELECT ─────────────────────────────────────────
            # Click Weekdays → banner appears. Click Weekends → grid is now empty.
            # Then CHECK only the wanted cells. This starts from a KNOWN empty
            # state, eliminating reliance on isChecked() for the main logic and
            # preventing the correction loop from double-toggling cells.
            # (The old "uncheck-unwanted" strategy was fatally flawed: if
            # isChecked() misreports cells as checked, the correction loop
            # re-clicks them, toggling them BACK to checked.)
            logger.info("set_schedule_grid: STRATEGY=clear-and-select "
                        "(click Weekdays+Weekends to clear, then CHECK %d cells)",
                        len(wanted))
            await _click_modal_btn("Weekdays")
            await asyncio.sleep(2.0)   # wait for banner to appear after 1st toggle
            await _click_modal_btn("Weekends")
            await _settle_and_scroll_bottom()  # wait 2s + scroll to bottom
            await _refresh_grid_coords_from_dom()
            cells_to_click   = sorted(wanted)
            click_action     = "CHECK"
            expected_toggles = len(wanted)

            for tag in cells_to_click:
                if await _click_cell(tag, click_action):
                    clicked += 1

            # Verify: scroll Save into view, re-read full grid state
            await asyncio.sleep(0.3)  # let React settle

            # Scroll Save button into view and re-read entire grid
            js_verify_and_scroll_save = """
(function() {
    var weekdaysBtn = null;
    var allBtns = document.querySelectorAll('button');
    for (var i = 0; i < allBtns.length; i++) {
        if (allBtns[i].textContent.trim() === 'Weekdays') { weekdaysBtn = allBtns[i]; break; }
    }
    if (!weekdaysBtn) return JSON.stringify({error: 'No Weekdays button'});
    var container = weekdaysBtn;
    for (var up = 0; up < 12; up++) { container = container.parentElement; if (!container) break; }

    var rows = [];
    var candidateRows = container.querySelectorAll('div[class*="StyledInlineChildren"]');
    for (var r = 0; r < candidateRows.length; r++) {
        var row = candidateRows[r];
        if (row.children.length === 7) {
            var ok = true;
            for (var c = 0; c < 7; c++) { if (!row.children[c].querySelector('svg')) { ok = false; break; } }
            if (ok) rows.push(row);
        }
    }
    if (rows.length < 6) {
        rows = [];
        var allDivs = container.querySelectorAll('div');
        for (var d = 0; d < allDivs.length; d++) {
            var div = allDivs[d];
            if (div.children.length === 7) {
                var ok2 = true;
                for (var c2 = 0; c2 < 7; c2++) { if (!div.children[c2].querySelector('svg')) { ok2 = false; break; } }
                if (ok2) rows.push(div);
            }
        }
    }
    if (rows.length < 6) {
        var vWkRect = weekdaysBtn.getBoundingClientRect();
        var vMinY = vWkRect.bottom - 5;
        rows = [];
        var allDivs3 = container.querySelectorAll('div');
        for (var d3 = 0; d3 < allDivs3.length; d3++) {
            var dv3 = allDivs3[d3];
            if (dv3.children.length === 7) {
                var dvR3 = dv3.getBoundingClientRect();
                if (dvR3.top >= vMinY && dvR3.height > 25 && dvR3.height < 200) {
                    var chOk = true;
                    for (var c4 = 0; c4 < 7; c4++) {
                        var chR4 = dv3.children[c4].getBoundingClientRect();
                        if (chR4.width < 15 || chR4.height < 15) { chOk = false; break; }
                    }
                    if (chOk) rows.push(dv3);
                }
            }
        }
        rows.sort(function(a, b) { return a.getBoundingClientRect().top - b.getBoundingClientRect().top; });
        if (rows.length > 6) rows = rows.slice(rows.length - 6);
    }

    // Re-read checked state for all cells
    function isChecked(cellDiv) {
        var style = window.getComputedStyle(cellDiv);
        var bg = style.backgroundColor;
        var innerDiv = cellDiv.querySelector('div');
        var innerBg = innerDiv ? window.getComputedStyle(innerDiv).backgroundColor : '';
        function isTealish(color) {
            if (!color || color === 'rgba(0, 0, 0, 0)' || color === 'transparent') return false;
            var m = color.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
            if (!m) return false;
            var r = parseInt(m[1]), g = parseInt(m[2]), b = parseInt(m[3]);
            if (r > 240 && g > 240 && b > 240) return false;
            if (r > 220 && g > 220 && b > 220 && Math.abs(r-g) < 15 && Math.abs(g-b) < 15) return false;
            return true;
        }
        if (isTealish(bg)) return true;
        if (isTealish(innerBg)) return true;
        var svg = cellDiv.querySelector('svg');
        if (svg) {
            var path = svg.querySelector('path');
            if (path) {
                var pathStyle = window.getComputedStyle(path);
                var stroke = pathStyle.stroke;
                if (stroke && stroke !== 'none' && stroke !== 'rgba(0, 0, 0, 0)') return true;
            }
        }
        if (cellDiv.getAttribute('aria-checked') === 'true') return true;
        if (cellDiv.getAttribute('aria-checked') === 'false') return false;
        return false;
    }

    var result = {cells: [], saveBtn: null};
    if (rows.length >= 6) {
        for (var ri = 0; ri < 6; ri++) {
            for (var ci = 0; ci < 7; ci++) {
                var cell = rows[ri].children[ci];
                result.cells.push({tag: ri * 7 + ci + 1, checked: isChecked(cell)});
            }
        }
    }

    // Scroll Save button into view
    var modalBtns = container.querySelectorAll('button');
    for (var j = 0; j < modalBtns.length; j++) {
        var btnTxt = modalBtns[j].textContent.trim();
        if (btnTxt === 'Save' || btnTxt === 'Save schedule') {
            modalBtns[j].scrollIntoView({behavior: 'instant', block: 'center'});
            var sRect = modalBtns[j].getBoundingClientRect();
            result.saveBtn = {x: Math.round(sRect.left + sRect.width / 2), y: Math.round(sRect.top + sRect.height / 2)};
            break;
        }
    }
    return JSON.stringify(result);
})()
"""
            verify_result = await cdp_client.send.Runtime.evaluate(
                params={"expression": js_verify_and_scroll_save, "returnByValue": True, "awaitPromise": True},
                session_id=session_id,
            )
            verify_raw = verify_result.get("result", {}).get("value", "{}")
            verify_info = json.loads(verify_raw) if isinstance(verify_raw, str) else verify_raw

            grid_verified = False
            if "cells" in verify_info and verify_info["cells"]:
                after_checked = {c["tag"] for c in verify_info["cells"] if c.get("checked")}
                logger.info("set_schedule_grid: AFTER clicks: checked=%s", sorted(after_checked))
                if after_checked == wanted:
                    logger.info("set_schedule_grid: VERIFIED — grid matches wanted state perfectly")
                    grid_verified = True
                else:
                    missing = wanted - after_checked
                    extra = after_checked - wanted
                    if missing:
                        logger.warning("set_schedule_grid: MISMATCH — still unchecked but wanted: %s",
                                       ", ".join(f"{t}({_tag_label(t)})" for t in sorted(missing)))
                    if extra:
                        logger.warning("set_schedule_grid: MISMATCH — checked but unwanted (likely isChecked false positive): %s",
                                       ", ".join(f"{t}({_tag_label(t)})" for t in sorted(extra)))
                    # Only correct MISSING cells (click to check them).
                    # NEVER try to uncheck "extra" cells — in clear-and-select
                    # mode we started from empty grid, so "extra" detections are
                    # isChecked() false positives. Clicking them would uncheck
                    # cells that are actually correct.
                    if missing:
                        logger.info("set_schedule_grid: CORRECTING %d missing cells (ignoring %d false-positive extras)...",
                                    len(missing), len(extra))
                        for corr_tag in sorted(missing):
                            if await _click_cell(corr_tag, "CORRECT-CHECK"):
                                clicked += 1
                        await asyncio.sleep(0.5)

                        verify2_result = await cdp_client.send.Runtime.evaluate(
                            params={"expression": js_verify_and_scroll_save, "returnByValue": True, "awaitPromise": True},
                            session_id=session_id,
                        )
                        verify2_raw = verify2_result.get("result", {}).get("value", "{}")
                        verify2_info = json.loads(verify2_raw) if isinstance(verify2_raw, str) else verify2_raw
                        if "cells" in verify2_info and verify2_info["cells"]:
                            after2_checked = {c["tag"] for c in verify2_info["cells"] if c.get("checked")}
                            logger.info("set_schedule_grid: AFTER CORRECTION: checked=%s", sorted(after2_checked))
                            still_missing = wanted - after2_checked
                            if not still_missing:
                                logger.info("set_schedule_grid: VERIFIED after correction — all wanted cells checked")
                                grid_verified = True
                            else:
                                logger.warning("set_schedule_grid: STILL MISSING after correction: %s",
                                               ", ".join(f"{t}({_tag_label(t)})" for t in sorted(still_missing)))
                            if verify2_info.get("saveBtn"):
                                save_btn = verify2_info["saveBtn"]
                    elif not missing and extra:
                        # No missing cells, only false-positive extras → treat as verified
                        logger.info("set_schedule_grid: no missing cells — treating as VERIFIED "
                                    "(ignoring %d isChecked false positives)", len(extra))
                        grid_verified = True

            # Click Save — ONLY if grid verified (don't save wrong state)
            save_clicked = False
            if verify_info and "saveBtn" in verify_info and verify_info["saveBtn"] and not save_btn:
                save_btn = verify_info["saveBtn"]

            if not grid_verified:
                msg = (
                    f"ERROR [clear-and-select]: wanted={len(wanted)}/42. "
                    "Grid state does NOT match wanted state — Save NOT clicked to avoid saving wrong schedule. "
                    "Do it manually."
                )
                logger.info("set_schedule_grid: %s", msg)
                return ActionResult(error=msg)

            if save_btn:
                await asyncio.sleep(0.2)
                logger.info("set_schedule_grid: clicking Save at (%d, %d)", save_btn["x"], save_btn["y"])
                await cdp_click(save_btn["x"], save_btn["y"])
                save_clicked = True
                clicked += 1

            if save_clicked:
                msg = f"SUCCESS [clear-and-select]: wanted={len(wanted)}/42"
            else:
                msg = f"PARTIAL [clear-and-select]: wanted={len(wanted)}/42. Save button not found — click Save manually."
            logger.info("set_schedule_grid: %s", msg)
            if not save_clicked:
                return ActionResult(error=msg)
            return ActionResult(extracted_content=msg)
        except Exception as e:
            logger.warning("set_schedule_grid failed: %s", e)
            return ActionResult(error=f"set_schedule_grid error: {e}")

    @tools.action(
        description=(
            "Click the leftmost (lowest/smallest value) button under 'Maximum discount amount' "
            "in the customer incentive modal. Always use this instead of manually clicking the "
            "max discount buttons. Call after the incentive modal is open and minimum subtotal is set. "
            "Returns the value of the button that was clicked."
        ),
    )
    async def click_leftmost_max_discount(reason: str, browser_session) -> ActionResult:
        """Programmatically click the first/leftmost max discount button via CDP."""
        try:
            import json as _json
            cdp_sess = await browser_session.get_or_create_cdp_session()
            cdp_cli = cdp_sess.cdp_client
            sess_id = cdp_sess.session_id

            js = """
(function() {
    var allEls = document.querySelectorAll('*');
    var labelY = -1;
    for (var i = 0; i < allEls.length; i++) {
        if (allEls[i].children.length === 0 &&
            allEls[i].textContent.trim() === 'Maximum discount amount') {
            var r = allEls[i].getBoundingClientRect();
            labelY = r.bottom;
            break;
        }
    }
    if (labelY < 0) return JSON.stringify({error: 'Maximum discount amount label not found'});

    var btns = document.querySelectorAll('button');
    var candidates = [];
    for (var j = 0; j < btns.length; j++) {
        var txt = btns[j].textContent.trim();
        if (txt.match(/^\\$\\d/) && btns[j].getBoundingClientRect().top > labelY - 10) {
            candidates.push(btns[j]);
        }
    }
    if (candidates.length === 0) return JSON.stringify({error: 'No $ buttons found below label'});

    candidates.sort(function(a, b) {
        var ar = a.getBoundingClientRect(), br = b.getBoundingClientRect();
        var yDiff = ar.top - br.top;
        if (Math.abs(yDiff) > 10) return yDiff;
        return ar.left - br.left;
    });

    var btn = candidates[0];
    btn.scrollIntoView({behavior: 'instant', block: 'nearest'});
    var rect = btn.getBoundingClientRect();
    return JSON.stringify({
        x: Math.round(rect.left + rect.width / 2),
        y: Math.round(rect.top + rect.height / 2),
        text: btn.textContent.trim()
    });
})()
"""
            eval_result = await cdp_cli.send.Runtime.evaluate(
                params={"expression": js, "returnByValue": True, "awaitPromise": True},
                session_id=sess_id,
            )
            raw_val = eval_result.get("result", {}).get("value", "{}")
            info = _json.loads(raw_val) if isinstance(raw_val, str) else raw_val

            if "error" in info:
                return ActionResult(error=info["error"])

            x, y, text = info.get("x", 0), info.get("y", 0), info.get("text", "?")
            if not (x and y):
                return ActionResult(error="Could not get button coordinates")

            await cdp_cli.send.Input.dispatchMouseEvent(
                params={"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1},
                session_id=sess_id,
            )
            await cdp_cli.send.Input.dispatchMouseEvent(
                params={"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1},
                session_id=sess_id,
            )
            logger.info("click_leftmost_max_discount: clicked '%s' at (%d,%d)", text, x, y)
            return ActionResult(extracted_content=f"Clicked leftmost max discount button: {text}")
        except Exception as e:
            logger.warning("click_leftmost_max_discount failed: %s", e)
            return ActionResult(error=f"click_leftmost_max_discount error: {e}")

    return tools

# --- IN USE: Login → Report creation → Report download (Phase 1 of main flow) ---
def _use_multilogin_session() -> bool:
    try:
        from shared.multilogin_browser import multilogin_enabled

        return multilogin_enabled() or bool(os.getenv("MULTILOGIN_CDP_URL", "").strip())
    except Exception:
        return False


def get_task_description_reports_only(
    email: str,
    password: str,
    start_date: str,
    end_date: str,
    *,
    session_prepared: bool = False,
) -> str:
    """Task that ends after downloading both reports (no campaign). Used so we can run analysis before campaign."""
    from shared.doordash_portal_tasks import (
        build_portal_entry_steps,
        build_post_login_reports_preamble,
        resolve_doordash_credentials,
    )

    resolved_email, resolved_password = resolve_doordash_credentials(email, password)
    if session_prepared:
        entry, s = build_post_login_reports_preamble(step_num=0)
    else:
        entry, s = build_portal_entry_steps(resolved_email, resolved_password, step_num=0)
    return f"""You are automating the DoorDash Merchant Portal. Complete the following steps in order. Stop after downloading both reports — do NOT create a campaign.
{entry}
=== STEP {s}: Generate Financial Report ===
{s}. On the Reports page, click "Create report". Select "Financial report" RADIO BUTTON, click "Next".
{s + 1}. LOCATIONS: Do NOT open or change store selection. Keep the default "All stores" selection as-is and click "Next".
{s + 2}. Choose "By date range". In each date field, CLEAR existing value completely and TYPE the exact date. Set Start date exactly to {start_date} and End date exactly to {end_date}. Verify both fields still show these exact values before proceeding. Click "Create report". WAIT UNTIL the report appears in the list (it may take several seconds to generate).

=== STEP {s + 3}: Download the Financial Report IMMEDIATELY ===
{s + 3}. WAIT until the newly created Financial report row is visible and its DOWNLOAD icon is visible/clickable. If not ready, wait 10 seconds and check again (repeat up to 6 times). When ready, click the DOWNLOAD icon for that Financial row. WAIT UNTIL the download completes.

=== STEP {s + 4}: Generate Marketing Report ===
{s + 4}. Click "Create report". Select "Marketing report" RADIO BUTTON, click "Next".

=== STEP {s + 5}: Configure Marketing Report (Step 2 of 2 — create exactly once) ===
{s + 5}. On the Marketing configuration screen (Step 2 of 2):
- CHANNELS: Do NOT click or change anything. "Marketplace" is already selected by default — leave it as-is. Do NOT select "Online Ordering".
- STORES: Do NOT change store selection. Keep default "All stores".
- DATE RANGE: If "One-time report" is shown, keep it selected. CLEAR both date fields completely and TYPE Start date exactly {start_date} and End date exactly {end_date}. Verify both fields still show these exact values (NOT the default last-7-days).
- Keep BOTH "Sponsored Listings" and "Promotions" checked.
- Click the red "Create report" button. WAIT UNTIL the new Marketing row appears in the reports list.
- Create Marketing exactly ONCE. If a Marketplace Marketing row for {start_date} – {end_date} already exists, skip creation and go to download.

=== STEP {s + 6}: Download the Marketing Report IMMEDIATELY ===
{s + 6}. Re-confirm Financial download completed. Click DOWNLOAD on the TOPMOST Marketplace Marketing row for {start_date} – {end_date}. WAIT UNTIL download completes.

=== DONE (stop here — no campaign) ===
When both reports are downloaded, use the done action to finish.
"""


def _get_retry_download_task(missing_reports: list[str]) -> str:
    """Generate a task to retry downloading missing reports from the already-open Reports page."""
    parts = []
    for report_type in missing_reports:
        if report_type == "Financial":
            parts.append(
                '- Find the most recently created "Financials" (or "Financial") report row in the reports table. '
                'WAIT until its DOWNLOAD icon is visible/clickable; if not ready, wait 10 seconds and re-check (up to 6 times). '
                'Then click the DOWNLOAD icon (arrow/download button) next to it. '
                'WAIT UNTIL the download completes (file appears in downloads folder).'
            )
        elif report_type == "Marketing":
            parts.append(
                '- Find the most recently created "Marketing" report row in the reports table. '
                'Click the DOWNLOAD icon (arrow/download button) next to it. '
                'WAIT UNTIL the download completes (file appears in downloads folder).'
            )
    steps = "\n".join(parts)
    return f"""
You are on the DoorDash Merchant Portal. The Reports page should already be open.
If you are not on the Reports page, click "Reports" in the left sidebar and WAIT for it to load.

Download the following missing report(s):
{steps}

IMPORTANT: Make sure to wait for each download to fully complete before proceeding to the next.
When done, use the done action. Summarize which reports were downloaded.
"""


def _get_regenerate_and_download_task(missing_reports: list[str], start_date: str, end_date: str) -> str:
    """Regenerate missing report type(s), then download them."""
    parts = []
    if "Financial" in missing_reports:
        parts.append(
            f"""FINANCIAL:
- Click "Create report"
- Select "Financial report", click Next
- Keep default "All stores", click Next
- CLEAR existing date values and TYPE exact date range: {start_date} to {end_date}
- Verify both date fields still show exact values before proceeding
- Click "Create report", wait for row to appear
- Wait until Financial row download icon is visible/clickable (poll every 10s up to 6 times)
- Download topmost Financial report
- Wait at least 5 seconds and confirm file appears in downloads"""
        )
    if "Marketing" in missing_reports:
        parts.append(
            f"""MARKETING:
- Click "Create report"
- Select "Marketing report", click Next
- On Step 2 of 2: do NOT change Channels — "Marketplace" is already selected; do NOT select "Online Ordering"
- Keep default "All stores"
- CLEAR both date fields and TYPE exact date range: {start_date} to {end_date}
- Verify both date fields still show exact values before proceeding
- Keep BOTH "Sponsored Listings" and "Promotions" checked
- Click "Create report" once, wait for row to appear
- Download topmost Marketplace Marketing report for {start_date} – {end_date}
- Wait until download completes"""
        )
    return (
        "You are on DoorDash Merchant Portal Reports. Regenerate and download ONLY the missing report types below.\n\n"
        + "\n\n".join(parts)
        + "\n\nWhen done, use done action and summarize what was regenerated and downloaded."
    )


def _selected_report_meta(report_type_id: str) -> dict[str, Any]:
    from shared.data_run_reports import DATA_RUN_REPORT_TYPES

    key = (report_type_id or "").strip().lower()
    meta = DATA_RUN_REPORT_TYPES.get(key)
    if not meta:
        raise ValueError(f"Unsupported report type: {report_type_id!r}")
    return meta


def _report_create_download_steps(
    report_type_id: str,
    *,
    start_date: str,
    end_date: str,
    step_offset: int = 1,
) -> tuple[str, int]:
    """Return prompt steps for one report type; returns (text, next_step_number)."""
    meta = _selected_report_meta(report_type_id)
    portal_label = meta["portal_label"]
    n = step_offset
    lines = [f"=== {meta['label'].upper()} ==="]

    if report_type_id == "marketing":
        lines.extend(
            [
                f'{n}. Click "Create report". Select "{portal_label}" RADIO BUTTON, click "Next".',
                (
                    f"{n + 1}. On Step 2 of 2: do NOT change Channels — \"Marketplace\" is already selected; "
                    f'do NOT select "Online Ordering". Keep default "All stores". '
                    f'CLEAR both date fields completely and TYPE Start {start_date}, End {end_date}. '
                    f"Do NOT accept DoorDash defaults (e.g. last 7 days). "
                    f'Verify BOTH fields still show exactly {start_date} and {end_date}. '
                    f'Keep BOTH "Sponsored Listings" and "Promotions" checked. '
                    f'Click "Create report" once. WAIT until the new row appears and its Time frame shows {start_date} – {end_date}.'
                ),
                (
                    f"{n + 2}. CONFIRM the TOPMOST new Marketplace {portal_label} row Time frame is {start_date} – {end_date}. "
                    f"If wrong dates, delete that row and recreate with the correct range. "
                    f"Click DOWNLOAD on the correct row. WAIT until the .zip download completes."
                ),
            ]
        )
        return "\n".join(lines), n + 3

    lines.extend(
        [
            f'{n}. Click "Create report". Select "{portal_label}" RADIO BUTTON, click "Next".',
            f'{n + 1}. Keep default "All stores" (do not change store selection), click "Next".',
            f"{n + 2}. Choose \"By date range\". CLEAR both date fields and TYPE Start {start_date}, End {end_date}. Verify values, then click \"Create report\". WAIT until the row appears.",
            f"{n + 3}. WAIT until the new {portal_label} row DOWNLOAD icon is visible (poll every 10s up to 6 times). Click DOWNLOAD. WAIT until the .zip download completes.",
        ]
    )
    return "\n".join(lines), n + 4


def get_task_description_selected_reports(
    email: str,
    password: str,
    start_date: str,
    end_date: str,
    report_types: list[str],
    *,
    session_prepared: bool = False,
) -> str:
    """Browser-use task: login (if needed) then create + download selected report zips only."""
    from shared.doordash_portal_tasks import (
        build_portal_entry_steps,
        build_post_login_reports_preamble,
        resolve_doordash_credentials,
    )

    ordered = list(report_types)
    report_labels = ", ".join(_selected_report_meta(r)["label"] for r in ordered)
    resolved_email, resolved_password = resolve_doordash_credentials(email, password)
    if session_prepared:
        portal_entry = build_post_login_reports_preamble(step_num=0)[0]
    else:
        portal_entry = build_portal_entry_steps(resolved_email, resolved_password, step_num=0)[0]
    header = (
        f"You are automating the DoorDash Merchant Portal. "
        f"Download ONLY these report types as .zip files (do not unzip): {report_labels}.\n"
        + portal_entry
    )

    body_parts: list[str] = []
    step = 1
    for rid in ordered:
        chunk, step = _report_create_download_steps(rid, start_date=start_date, end_date=end_date, step_offset=step)
        body_parts.append(chunk)

    footer = """
=== DONE ===
When every requested report .zip has finished downloading, use the done action.
Do NOT open or extract zip files. Summarize which report types were downloaded.
"""
    return header + "\n".join(body_parts) + footer


def get_task_description_one_selected_report(
    email: str,
    password: str,
    start_date: str,
    end_date: str,
    report_type_id: str,
    *,
    include_portal_entry: bool = False,
    session_prepared: bool = False,
) -> str:
    """Single report type: optional portal entry, then create + download one .zip."""
    from shared.doordash_portal_tasks import (
        build_portal_entry_steps,
        build_post_login_reports_preamble,
        resolve_doordash_credentials,
    )

    resolved_email, resolved_password = resolve_doordash_credentials(email, password)
    meta = _selected_report_meta(report_type_id)
    parts: list[str] = [
        f"You are automating DoorDash Merchant Portal. Download ONLY one {meta['label']} .zip "
        f"for date range {start_date} to {end_date}. Complete this report fully before stopping.",
    ]
    if include_portal_entry:
        if session_prepared:
            parts.append(build_post_login_reports_preamble(step_num=0)[0])
        else:
            parts.append(build_portal_entry_steps(resolved_email, resolved_password, step_num=0)[0])
    else:
        parts.append(
            "\nYou should already be on the DoorDash Reports page. "
            "If not, open Reports from the sidebar first.\n"
        )
    chunk, _ = _report_create_download_steps(
        report_type_id, start_date=start_date, end_date=end_date, step_offset=1
    )
    parts.append(chunk)
    parts.append(
        "\n=== DONE ===\n"
        f"When the {meta['label']} .zip has finished downloading, use the done action. "
        "Do NOT start other report types."
    )
    return "\n".join(parts)


def _discover_selected_downloads(
    download_dir: Path,
    report_types: list[str],
    *,
    baseline_files: set[Path] | None = None,
    min_mtime: float | None = None,
    zip_only: bool = True,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[dict[str, Optional[Path]], dict[str, Any]]:
    """Map report type id → newest matching .zip (or file if zip_only=False)."""
    from shared.data_run_reports import DATA_RUN_REPORT_TYPES, zip_filename_matches_date_range

    download_dir = Path(download_dir)
    found: dict[str, Optional[Path]] = {rid: None for rid in report_types}
    if not download_dir.is_dir():
        return found, {"considered_files": [], "filtered_out": []}

    existing = baseline_files or set()
    candidates: list[tuple[float, Path]] = []
    filtered_out: list[str] = []
    for f in _list_report_files(download_dir):
        if zip_only and f.suffix.lower() != ".zip":
            filtered_out.append(f"{f.name}:not_zip")
            continue
        st = f.stat()
        if f in existing:
            filtered_out.append(f"{f.name}:baseline")
            continue
        if min_mtime is not None and st.st_mtime < min_mtime:
            filtered_out.append(f"{f.name}:old")
            continue
        if start_date and end_date and not zip_filename_matches_date_range(f, start_date, end_date):
            filtered_out.append(f"{f.name}:date_mismatch")
            continue
        candidates.append((st.st_mtime, f))
    candidates.sort(key=lambda x: x[0], reverse=True)

    assigned: set[Path] = set()
    for rid in report_types:
        meta = DATA_RUN_REPORT_TYPES[rid]
        keywords = tuple(k.lower() for k in meta.get("filename_keywords") or ())
        for _mtime, path in candidates:
            if path in assigned:
                continue
            name_lower = path.name.lower()
            if any(kw in name_lower for kw in keywords):
                found[rid] = path
                assigned.add(path)
                break

    diagnostics = {
        "considered_files": [p.name for _m, p in candidates],
        "filtered_out": filtered_out,
        "detected": {rid: (found[rid].name if found[rid] else None) for rid in report_types},
    }
    return found, diagnostics


def _get_retry_download_task_selected(missing: list[str]) -> str:
    parts = []
    for label in missing:
        parts.append(
            f'- Find the most recent "{label}" report row. WAIT for DOWNLOAD icon (poll 10s up to 6 times). '
            f"Click DOWNLOAD and WAIT until the .zip completes."
        )
    return (
        "You are on DoorDash Reports. Download these missing report types:\n"
        + "\n".join(parts)
        + "\nUse done when finished."
    )


def _get_regenerate_selected_task(
    missing_type_ids: list[str],
    start_date: str,
    end_date: str,
) -> str:
    parts = []
    for rid in missing_type_ids:
        chunk, _ = _report_create_download_steps(rid, start_date=start_date, end_date=end_date, step_offset=1)
        parts.append(chunk)
    return (
        "Regenerate and download ONLY these missing report types on DoorDash Reports:\n\n"
        + "\n\n".join(parts)
        + "\n\nUse done when all requested .zip files are downloaded."
    )


async def _cancel_agent_task(agent_task: asyncio.Task) -> None:
    if not agent_task.done():
        agent_task.cancel()
        try:
            await agent_task
        except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
            pass


async def _discover_report_path(
    download_dir: Path,
    report_type_id: str,
    *,
    baseline_files: set[Path],
    min_mtime: float,
    zip_only: bool,
    start_date: str,
    end_date: str,
) -> Optional[Path]:
    found, diag = _discover_selected_downloads(
        download_dir,
        [report_type_id],
        baseline_files=baseline_files,
        min_mtime=min_mtime,
        zip_only=zip_only,
        start_date=start_date,
        end_date=end_date,
    )
    path = found.get(report_type_id)
    if path:
        logger.info("DoorDash: discovered %s → %s", report_type_id, path.name)
    elif diag.get("filtered_out"):
        logger.info("DoorDash: %s not matched (filtered: %s)", report_type_id, diag.get("filtered_out"))
    return path


async def _run_single_report_agent(
    *,
    agent: Any,
    download_dir: Path,
    report_type_id: str,
    baseline_files: set[Path],
    run_started_at: float,
    zip_only: bool,
    start_date: str,
    end_date: str,
) -> Optional[Path]:
    """Run one browser-use agent task; poll until this report's zip lands on disk."""
    agent_task = asyncio.create_task(
        asyncio.wait_for(agent.run(), timeout=AGENT_SINGLE_REPORT_TIMEOUT)
    )
    try:
        while not agent_task.done():
            path = await _discover_report_path(
                download_dir,
                report_type_id,
                baseline_files=baseline_files,
                min_mtime=run_started_at,
                zip_only=zip_only,
                start_date=start_date,
                end_date=end_date,
            )
            if path:
                logger.info("DoorDash: %s zip on disk — stopping agent early", report_type_id)
                await _cancel_agent_task(agent_task)
                return path
            await asyncio.sleep(3)
        history = await agent_task
        if history and getattr(history, "final_result", None):
            logger.info("DoorDash (%s): %s", report_type_id, history.final_result)
    except asyncio.TimeoutError:
        logger.warning("DoorDash: %s timed out after %ss", report_type_id, AGENT_SINGLE_REPORT_TIMEOUT)
        await _cancel_agent_task(agent_task)
    except Exception as exc:
        logger.warning("DoorDash: %s agent failed: %s", report_type_id, exc)
        await _cancel_agent_task(agent_task)
    return await _discover_report_path(
        download_dir,
        report_type_id,
        baseline_files=baseline_files,
        min_mtime=run_started_at,
        zip_only=zip_only,
        start_date=start_date,
        end_date=end_date,
    )


async def run_selected_reports(
    download_dir: Path,
    email: str,
    password: str,
    start_date: str,
    end_date: str,
    report_types: list[str],
    *,
    zip_only: bool = True,
) -> dict[str, Optional[Path]]:
    """
    Login + create + download requested DoorDash report types **one at a time**.
    Returns map of report_type_id → downloaded file path (.zip preferred).
    """
    from browser_use import Agent

    from shared.data_run_reports import normalize_report_type_ids

    ordered = normalize_report_type_ids(report_types)
    download_dir = Path(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "DoorDash (browser-use): sequential selected reports | types=%s | %s to %s",
        ordered,
        start_date,
        end_date,
    )
    baseline_files = set(_list_report_files(download_dir))
    run_started_at = time.time()
    llm = _get_llm()
    browser = _get_browser(download_dir, doordash_email=email)
    found: dict[str, Optional[Path]] = {rid: None for rid in ordered}

    await _prepare_portal_session(browser, email, password)

    try:
        for idx, rid in enumerate(ordered):
            logger.info(
                "DoorDash: === report %d/%d: %s ===",
                idx + 1,
                len(ordered),
                rid,
            )
            task = get_task_description_one_selected_report(
                email=email,
                password=password,
                start_date=start_date,
                end_date=end_date,
                report_type_id=rid,
                include_portal_entry=(idx == 0),
                session_prepared=True,
            )
            path = await _run_single_report_agent(
                agent=Agent(task=task, llm=llm, browser=browser),
                download_dir=download_dir,
                report_type_id=rid,
                baseline_files=baseline_files,
                run_started_at=run_started_at,
                zip_only=zip_only,
                start_date=start_date,
                end_date=end_date,
            )

            if not path:
                label = _selected_report_meta(rid)["retry_label"]
                logger.warning("DoorDash: %s missing — retry download only", rid)
                retry_agent = Agent(
                    task=_get_retry_download_task_selected([label]),
                    llm=llm,
                    browser=browser,
                )
                try:
                    await asyncio.wait_for(retry_agent.run(), timeout=300)
                except Exception as retry_err:
                    logger.warning("DoorDash retry download failed for %s: %s", rid, retry_err)
                path = await _discover_report_path(
                    download_dir,
                    rid,
                    baseline_files=baseline_files,
                    min_mtime=run_started_at,
                    zip_only=zip_only,
                    start_date=start_date,
                    end_date=end_date,
                )

            if not path:
                logger.warning("DoorDash: %s still missing — regenerate + download", rid)
                regen_agent = Agent(
                    task=_get_regenerate_selected_task([rid], start_date, end_date),
                    llm=llm,
                    browser=browser,
                )
                try:
                    await asyncio.wait_for(regen_agent.run(), timeout=420)
                except Exception as regen_err:
                    logger.warning("DoorDash regenerate failed for %s: %s", rid, regen_err)
                path = await _discover_report_path(
                    download_dir,
                    rid,
                    baseline_files=baseline_files,
                    min_mtime=run_started_at,
                    zip_only=zip_only,
                    start_date=start_date,
                    end_date=end_date,
                )

            found[rid] = path
            if path:
                logger.info("DoorDash: completed %s → %s", rid, path)
            else:
                logger.error("DoorDash: FAILED %s — no matching zip in %s", rid, download_dir)

        return found
    finally:
        await _kill_browser(browser)


def _inspect_marketing_zip(path: Optional[Path]) -> dict[str, Any]:
    """Inspect marketing zip for promotion/sponsored components."""
    if not path or path.suffix.lower() != ".zip":
        return {"promotion_csv": None, "sponsored_csv": None, "entries": 0}
    try:
        with zipfile.ZipFile(path, "r") as z:
            names = [n.upper() for n in z.namelist()]
        has_promo = any("MARKETING_PROMOTION" in n and n.endswith(".CSV") for n in names)
        has_sponsored = any("MARKETING_SPONSORED" in n and n.endswith(".CSV") for n in names)
        return {"promotion_csv": has_promo, "sponsored_csv": has_sponsored, "entries": len(names)}
    except Exception:
        return {"promotion_csv": None, "sponsored_csv": None, "entries": 0}


# --- IN USE: Campaign creation with subtotal + slot tags (Phase 2, per store per subtotal) ---
def get_task_description_campaign_for_subtotal_combo(
    combo: dict,
    *,
    include_session_preamble: bool = True,
) -> str:
    store_id = str(combo.get("store_id", "")).strip()
    store_name = str(combo.get("store_name", "")).strip()
    min_subtotal = combo.get("min_subtotal", 10)
    try:
        min_subtotal = int(round(float(min_subtotal)))
    except (TypeError, ValueError):
        min_subtotal = 10
    slot_tags = combo.get("slot_tags") or []
    if not isinstance(slot_tags, (list, tuple)):
        slot_tags = []
    slot_tags = [int(t) for t in slot_tags if t is not None and str(t).strip() != ""]
    campaign_name = str(combo.get("campaign_name", f"TODC-{store_id}-${min_subtotal}")).strip() or f"TODC-{store_id}-${min_subtotal}"
    tags_str = ", ".join(str(t) for t in sorted(slot_tags))

    # Name-first store search (N1 fix: DoorDash search matches names; numeric IDs often fail)
    store_id_digits = store_id.replace(",", "")
    try:
        _n = float(store_id_digits)
        store_id_digits = str(int(_n)) if _n == int(_n) else store_id_digits
    except (TypeError, ValueError):
        pass
    if store_name:
        store_search_primary = f'"{store_name}"'
    else:
        store_search_primary = (
            f"the exact location name as shown in the store list "
            f"(internal id {store_id_digits or store_id} is for your reference only — "
            f"do not type .0 or search the id first)"
        )

    selected_set = set(slot_tags)
    all_tags = set(range(1, 43))
    unselected_set = all_tags - selected_set

    _GRID_ROWS = ["Overnight", "Breakfast", "Lunch", "Afternoon", "Dinner", "Late night"]
    _GRID_COLS = ["Mon", "Tue", "Wed", "Thur", "Fri", "Sat", "Sun"]

    def _group_by_row(tag_set):
        rows = {}
        for t in sorted(tag_set):
            row_idx = (t - 1) // 7
            row_name = _GRID_ROWS[row_idx]
            col_name = _GRID_COLS[(t - 1) % 7]
            rows.setdefault(row_name, []).append((t, col_name))
        return rows

    # Build fallback manual instructions (used ONLY if set_schedule_grid fails twice)
    if len(selected_set) == 42:
        manual_fallback = "All 42 cells should already be selected. Just click Save."
    elif len(unselected_set) <= 20:
        grouped = _group_by_row(unselected_set)
        lines = []
        for row_name, cells in grouped.items():
            cols = ", ".join(col for _, col in cells)
            lines.append(f"  - {row_name} row: click {cols}")
        manual_fallback = f"DESELECT these {len(unselected_set)} cells (click each ONCE):\n" + "\n".join(lines) + "\n  Then click Save."
    else:
        grouped = _group_by_row(selected_set)
        lines = []
        for row_name, cells in grouped.items():
            cols = ", ".join(col for _, col in cells)
            lines.append(f"  - {row_name} row: click {cols}")
        manual_fallback = (
            f"Click Weekdays ONCE, then Weekends ONCE (grid now empty). "
            f"Then SELECT these {len(selected_set)} cells (click each ONCE):\n"
            + "\n".join(lines)
            + "\n  Then click Save. NEVER click Weekdays/Weekends again."
        )

    schedule_instructions = f"""- IMPORTANT: Use the set_schedule_grid action to configure the grid automatically.
- Call: set_schedule_grid(wanted_tags="{tags_str}")
- This action programmatically checks/unchecks the correct cells and clicks Save. It is 100% reliable.
- Do NOT manually click any grid cells, "Weekdays", or "Weekends" buttons. The action handles everything.
- If set_schedule_grid returns SUCCESS, proceed to STEP 4B immediately.
- If set_schedule_grid returns PARTIAL (Save not found), click "Save" manually once, then proceed to STEP 4B.
- If set_schedule_grid returns ERROR twice, do it manually: {manual_fallback}"""

    session_email = str(combo.get("doordash_email") or os.getenv("DOORDASH_EMAIL", "")).strip()
    session_password = str(combo.get("doordash_password") or os.getenv("DOORDASH_PASSWORD", "")).strip()
    preamble_block = ""
    if include_session_preamble:
        from shared.doordash_portal_tasks import build_campaign_session_preamble

        preamble_block = build_campaign_session_preamble(session_email, session_password or None) + "\n"

    return f"""
ROLE: You are automating campaign creation on DoorDash Merchant Portal. You are already logged in.

{preamble_block}RULES:
- Do NOT go to the login page or create/download reports.
- Do NOT click "Get started" (that is for BOGO, not discount campaigns).
- After "Run a campaign", use ONLY "Offer a discount promotion" under "More ways to help you grow" (carousel: click the right arrow twice, then Select). Do not pick "Smart campaign", "Advertise to all customers", or other template cards for this flow.
- Do NOT click "Create promotion" until step 6 explicitly says to.
- If a modal fails to open after clicking Edit, wait 3s, scroll to make section visible, click Edit again ONCE.
- In "Choose stores", search by store NAME. Searching numeric store IDs often shows "No stores found".

CAMPAIGN: {campaign_name} | STORE: {store_id} ({store_name if store_name else "N/A"}) | SUBTOTAL: ${min_subtotal} | TAGS: {tags_str}

STEP 1 — Open campaign builder:
- Click "Marketing" in the left sidebar. Wait for page to load.
- Click "Run a campaign". Wait until you see "Recommended for you" and the "More ways to help you grow" section (carousel of cards).
- Scroll the main page if needed so "More ways to help you grow" and its carousel arrows are fully visible.
- In "More ways to help you grow", click the RIGHT carousel side arrow (next slide) EXACTLY TWO TIMES. Wait 1–2s after each click for the slide to change (pagination dots should move; you want the third slide).
- VERIFY the visible card title is "Offer a discount promotion". If it is not, use the left/right side arrows until that exact card is showing.
- Click "Select" on the "Offer a discount promotion" card. Do NOT use "Smart campaign", "Advertise to all customers", or other carousel cards for this flow.
- Click "Customize your campaign" when it appears (right panel or next step). Wait for the full campaign setup form to load, then continue with the steps below.

STEP 2 — Select store ("Choose stores" modal):
- Click Edit (pencil) next to "Stores". Wait for the modal.
- Click "Select All" to deselect all stores (so you start from none / wrong stores cleared).
- Clear the search field completely if it shows an old query. Do NOT paste a number with ".0" in it.
- PRIMARY: Search by STORE NAME. Type this in the search field: {store_search_primary}
- Wait for results. Select the ONE checkbox that corresponds to this campaign's store for {store_name or store_id_digits or store_id}. If "No stores found", clear search and try a shorter phrase from the name (first 2–4 words), then try again.
- LAST RESORT ONLY if name search fails: search plain digits with NO decimal point: {store_id_digits or store_id} (never "22978566.0"-style values).
- Select ONLY that store. Click "Save".

STEP 3 — Set customer incentive:
- Click Edit (pencil) next to "Customer incentive". Wait for modal.
- Click "15%" radio button.
- Click "Custom" under Minimum subtotal. Click the input field.
- Select all text (triple-click), type: {min_subtotal}
- Wait 2s. VERIFY field shows {min_subtotal} or ${min_subtotal}. If it shows $25 or wrong value, clear and retype.
- IMPORTANT: Use the click_leftmost_max_discount action to select the lowest maximum discount amount. Do NOT manually click any max discount button.
- Click "Save".

STEP 3B — Target audience (after Customer incentive, BEFORE Scheduling / slots):
- Click Edit (pencil) next to "Target audience" on the campaign summary. WAIT for the "Set target audience" modal.
- Select the **"All customers"** radio button (subtitle: "Everyone within your business' delivery radius"). Do NOT leave "Smart targeting" selected.
- Click the red **"Save"** button. WAIT until the modal closes and the summary reflects the change (target audience should show All customers, not only Smart targeting).

STEP 4 — Set schedule:
- Click Edit (pencil) next to "Scheduling". Wait for modal with grid.
- Click "Set a custom schedule". Wait for grid.
- Grid: 6 rows (Overnight, Breakfast, Lunch, Afternoon, Dinner, Late night) x 7 cols (Mon-Sun).
{schedule_instructions}

STEP 4B — Re-confirm Maximum discount amount (MANDATORY after schedule):
- Click Edit (pencil) next to "Customer incentive". Wait for modal to open.
- IMPORTANT: Use the click_leftmost_max_discount action to select the lowest maximum discount amount. Do NOT manually click any max discount button.
- Click "Save".
- This step is REQUIRED because DoorDash may change available max discount options after the schedule is modified.

STEP 5 — Set campaign name (MUST complete fully before moving to Step 6):
- Click Edit (pencil) next to "Campaign name". Wait for the name input field to appear.
- Triple-click the input field to select all existing text, then type exactly: {campaign_name}
- Click "Save". WAIT until the modal closes and the campaign summary shows "{campaign_name}".
- CRITICAL: Do NOT click "Create promotion" until this Save is confirmed. If the modal is still open, click Save again.

STEP 6 — Final verify and create (do NOT skip):
- BEFORE clicking "Create promotion", read the campaign summary panel:
  - Confirm **Target audience** is **All customers** (or equivalent). If it still says Smart targeting only, go back to STEP 3B and fix it.
  - Confirm it shows "${min_subtotal}" (not $25 unless target is $25). If wrong, click Edit next to "Customer incentive", fix it, Save.
  - Confirm campaign name shows "{campaign_name}".
- Click "Create promotion". Wait for success confirmation.
- IMPORTANT: If you see a message like "The details of this campaign are the same as one of your live campaigns" or any duplication warning, do NOT try to fix it. Just use the done action immediately and say: "{campaign_name}" DUPLICATE for store {store_id}.

DONE: Use done action. Say: "{campaign_name}" created for store {store_id}.
"""


def _get_llm():
    """Use local vLLM server (Qwen2.5-VL-7B-AWQ) for browser navigation."""
    from langchain_openai import ChatOpenAI

    base_url = os.getenv("VLLM_BROWSER_URL", "http://35.224.64.57:8002/v1")
    return ChatOpenAI(
        model=os.getenv("VLLM_BROWSER_MODEL", "Qwen/Qwen2.5-VL-7B-Instruct-AWQ"),
        base_url=base_url,
        api_key="none",
        temperature=0.0,
    )


def _get_browser(
    download_dir: Path,
    keep_alive: bool = False,
    *,
    doordash_email: str | None = None,
):
    """Browser for DoorDash automation (Multilogin, CDP, or local Chrome)."""
    from shared.browser_use_factory import create_browser_use_browser

    return create_browser_use_browser(
        download_dir, keep_alive=keep_alive, doordash_email=doordash_email
    )


async def _prepare_portal_session(
    browser,
    email: str,
    password: str,
    *,
    operator_name: str | None = None,
) -> None:
    """Uniform logout → credential login → Reports (native) or MLX warmup."""
    from shared.doordash_browser_use_login import prepare_doordash_browser_session

    ok = await prepare_doordash_browser_session(
        browser,
        email,
        password,
        operator_name=operator_name,
    )
    if not ok:
        raise RuntimeError(f"DoorDash portal login failed for {email}")


async def _relogin_portal_session(
    browser,
    email: str,
    password: str,
    *,
    attempts: int = 2,
) -> bool:
    """Re-login after browser restart (same uniform flow)."""
    for relogin_attempt in range(1, attempts + 1):
        try:
            await asyncio.wait_for(
                _prepare_portal_session(browser, email, password),
                timeout=AGENT_LOGIN_TIMEOUT,
            )
            logger.info("--- Re-login successful (attempt %d) ---", relogin_attempt)
            return True
        except asyncio.TimeoutError:
            logger.warning("--- Re-login attempt %d timed out ---", relogin_attempt)
        except Exception as e:
            logger.warning("--- Re-login attempt %d failed: %s ---", relogin_attempt, e)
    return False


def _peek_zip_type(path: Path) -> str:
    """
    Inspect ZIP contents to classify as 'financial', 'marketing', or ''.
    Used as fallback when filename has no recognizable keyword.
    """
    try:
        with zipfile.ZipFile(path, "r") as z:
            names_upper = " ".join(z.namelist()).upper()
        if "FINANCIAL_DETAILED" in names_upper or ("FINANCIAL" in names_upper and "MARKETING" not in names_upper):
            return "financial"
        if "MARKETING_PROMOTION" in names_upper or "MARKETING_SPONSORED" in names_upper or "MARKETING" in names_upper:
            return "marketing"
    except Exception:
        pass
    return ""


def _list_report_files(download_dir: Path) -> list[Path]:
    """List candidate report files sorted by mtime desc."""
    download_dir = Path(download_dir)
    if not download_dir.is_dir():
        return []

    all_files: list[tuple[float, Path]] = []
    for ext in ("*.csv", "*.zip", "*.xlsx"):
        for f in download_dir.glob(ext):
            if f.is_file():
                all_files.append((f.stat().st_mtime, f))
    all_files.sort(key=lambda x: x[0], reverse=True)
    return [f for _mtime, f in all_files]


def _combined_has_financial_sheets(path: Path) -> bool:
    """True when combined workbook includes Day-Slot sheets needed for campaigns."""
    try:
        import openpyxl

        wb = openpyxl.load_workbook(path, read_only=True)
        return any("Day-Slot" in name for name in wb.sheetnames)
    except Exception:
        return False


def _discover_downloads(
    download_dir: Path,
    *,
    baseline_files: set[Path] | None = None,
    min_mtime: float | None = None,
) -> Tuple[Optional[Path], Optional[Path], dict[str, Any]]:
    """Find financial + marketing zips in download_dir and system Downloads."""
    from shared.doordash_report_discovery import discover_doordash_reports

    return discover_doordash_reports(
        download_dir,
        baseline_files=baseline_files,
        min_mtime=min_mtime,
        relocate_external=True,
    )


async def _kill_browser(browser) -> None:
    """Gracefully kill/close browser and stop Multilogin profile if applicable."""
    from shared.browser_use_factory import close_browser_use_browser

    await close_browser_use_browser(browser)


async def run_reports_only(
    download_dir: Path,
    email: str,
    password: str,
    start_date: str,
    end_date: str,
) -> Tuple[Optional[Path], Optional[Path]]:
    """
    Run only login + report creation + download. Stops before campaign.
    Returns (marketing_download_path, financial_download_path) for analysis agents.
    """
    from browser_use import Agent

    download_dir = Path(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    task = get_task_description_reports_only(
        email=email,
        password=password,
        start_date=start_date,
        end_date=end_date,
        session_prepared=True,
    )
    logger.info("DoorDash (browser-use): Starting reports-only run (login, reports, download)")
    baseline_files = set(_list_report_files(download_dir))
    run_started_at = time.time()
    llm = _get_llm()
    browser = _get_browser(download_dir, doordash_email=email)
    try:
        await _prepare_portal_session(browser, email, password)
        from shared.cdp_downloads import configure_browser_download_dir

        await configure_browser_download_dir(browser, download_dir)
        agent = Agent(task=task, llm=llm, browser=browser)

        async def _run_agent():
            return await asyncio.wait_for(agent.run(), timeout=AGENT_REPORTS_TIMEOUT)

        agent_task = asyncio.create_task(_run_agent())
        try:
            while not agent_task.done():
                marketing_path, financial_path, _diag = _discover_downloads(
                    download_dir,
                    baseline_files=baseline_files,
                    min_mtime=run_started_at,
                )
                if marketing_path and financial_path:
                    logger.info(
                        "DoorDash (browser-use): Both reports on disk — stopping browser-use early"
                    )
                    agent_task.cancel()
                    try:
                        await agent_task
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                    except Exception as early_err:
                        logger.debug(
                            "DoorDash (browser-use): agent task ended after early stop: %s",
                            early_err,
                        )
                    return (marketing_path, financial_path)
                await asyncio.sleep(3)

            history = await agent_task
            if history and history.final_result:
                logger.info("DoorDash (browser-use): %s", history.final_result)
        finally:
            if not agent_task.done():
                agent_task.cancel()
                try:
                    await agent_task
                except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                    pass

        marketing_path, financial_path, diag = _discover_downloads(
            download_dir,
            baseline_files=baseline_files,
            min_mtime=run_started_at,
        )
        logger.info(
            "DoorDash (browser-use): discovery after initial run | considered=%s filtered=%s detected={marketing:%s, financial:%s}",
            diag.get("considered_files"),
            diag.get("filtered_out"),
            diag.get("marketing"),
            diag.get("financial"),
        )

        # Retry missing report(s) in deterministic sequence before giving up.
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            if financial_path and marketing_path:
                break
            missing: list[str] = []
            if not financial_path:
                missing.append("Financial")
            if not marketing_path:
                missing.append("Marketing")
            logger.warning(
                "DoorDash (browser-use): Missing report(s) after attempt %d: %s. Running retry sequence.",
                attempt,
                ", ".join(missing),
            )
            retry_task = _get_retry_download_task(missing)
            retry_agent = Agent(task=retry_task, llm=llm, browser=browser)
            try:
                await asyncio.wait_for(retry_agent.run(), timeout=300)
                marketing_path, financial_path, diag = _discover_downloads(
                    download_dir,
                    baseline_files=baseline_files,
                    min_mtime=run_started_at,
                )
                logger.info(
                    "DoorDash (browser-use): discovery after retry %d | considered=%s filtered=%s detected={marketing:%s, financial:%s}",
                    attempt,
                    diag.get("considered_files"),
                    diag.get("filtered_out"),
                    diag.get("marketing"),
                    diag.get("financial"),
                )
            except Exception as retry_err:
                logger.warning(
                    "DoorDash (browser-use): Retry download failed on attempt %d: %s",
                    attempt,
                    retry_err,
                )

        if not (financial_path and marketing_path):
            missing: list[str] = []
            if not financial_path:
                missing.append("Financial")
            if not marketing_path:
                missing.append("Marketing")
            logger.warning(
                "DoorDash (browser-use): Still missing after download retries: %s. Running regenerate-and-download fallback.",
                ", ".join(missing),
            )
            regen_task = _get_regenerate_and_download_task(missing, start_date, end_date)
            regen_agent = Agent(task=regen_task, llm=llm, browser=browser)
            try:
                await asyncio.wait_for(regen_agent.run(), timeout=420)
                marketing_path, financial_path, diag = _discover_downloads(
                    download_dir,
                    baseline_files=baseline_files,
                    min_mtime=run_started_at,
                )
                logger.info(
                    "DoorDash (browser-use): discovery after regeneration | considered=%s filtered=%s detected={marketing:%s, financial:%s}",
                    diag.get("considered_files"),
                    diag.get("filtered_out"),
                    diag.get("marketing"),
                    diag.get("financial"),
                )
            except Exception as regen_err:
                logger.warning(
                    "DoorDash (browser-use): Regenerate-and-download fallback failed: %s",
                    regen_err,
                )

        if financial_path:
            logger.info("DoorDash (browser-use): Financial report at %s", financial_path)
        if marketing_path:
            logger.info("DoorDash (browser-use): Marketing report at %s", marketing_path)
            mdiag = _inspect_marketing_zip(marketing_path)
            logger.info(
                "DoorDash (browser-use): Marketing zip diagnostics | promotion_csv=%s sponsored_csv=%s entries=%s",
                mdiag.get("promotion_csv"),
                mdiag.get("sponsored_csv"),
                mdiag.get("entries"),
            )
        return (marketing_path, financial_path)
    finally:
        await _kill_browser(browser)


# --- IN USE: Main flow — Login → Reports → Download → Analysis → Campaigns (subtotal+tags) for all stores/subtotals ---
async def run_reports_then_analysis_then_campaign(
    download_dir: Path,
    email: str,
    password: str,
    start_date: str,
    end_date: str,
    analysis_callback: Callable[[Optional[Path], Optional[Path]], Awaitable[Optional[Path]]],
    campaigns_only_combined_path: Optional[Path] = None,
) -> None:
    """
    Single browser session: login → reports → download → (browser stays open) →
    run analysis_callback(marketing_path, financial_path) → returns combined_path →
    for each (store, day, slot) combo from combined_analysis Day-Slot sheets, run campaign (no login again) → close browser.

    If campaigns_only_combined_path is provided, skip Phase 1 (reports) and analysis entirely.
    Just login and run campaigns from the existing combined analysis file.

    Store IDs come only from the logged-in account's combined_analysis sheets ("Day-Slot - {StoreID}"). No env store IDs.
    """
    from browser_use import Agent

    try:
        from agents.campaign_params import (
            get_all_campaign_combos_from_combined_analysis,
            get_campaign_combos_from_slots_and_combined,
            ensure_campaigns_executed_csv,
            log_campaign_executed,
        )
    except ImportError:
        get_all_campaign_combos_from_combined_analysis = None
        get_campaign_combos_from_slots_and_combined = None
        ensure_campaigns_executed_csv = None
        log_campaign_executed = None

    download_dir = Path(download_dir)
    project_root = Path(__file__).resolve().parent.parent
    slots_csv_path = project_root / "slots.csv"
    download_dir.mkdir(parents=True, exist_ok=True)

    llm = _get_llm()
    browser = _get_browser(download_dir, keep_alive=True, doordash_email=email)

    # --- CAMPAIGNS-ONLY MODE: skip reports & analysis, just login and run campaigns ---
    if campaigns_only_combined_path and Path(campaigns_only_combined_path).is_file():
        combined_path = Path(campaigns_only_combined_path)
        logger.info("=" * 70)
        logger.info("CAMPAIGNS-ONLY MODE — skipping reports & analysis")
        logger.info("  Email: %s", email)
        logger.info("  Combined analysis: %s", combined_path)
        logger.info("  Download dir: %s", download_dir)
        logger.info("=" * 70)
        push_to_slack(f"▶️ *Campaigns only* — using {combined_path.name}")

        from shared.doordash_portal_tasks import resolve_doordash_credentials

        resolved_email, resolved_password = resolve_doordash_credentials(email, password)
        try:
            await _prepare_portal_session(browser, email, password)
            logger.info("Login successful")
            push_to_slack(slack_msg.portal_logged_in())
        except Exception as e:
            await _kill_browser(browser)
            push_to_slack(slack_msg.portal_login_failed(detail=str(e)))
            raise e

        # Read combos from Campaign Mappings, skip Successful ones
        all_combos = read_campaign_combos_from_mappings(combined_path)
        if not all_combos:
            logger.warning("No campaign mappings found in %s", combined_path)
            await _kill_browser(browser)
            return
        before = len(all_combos)
        combos = [c for c in all_combos if c.get("status") != "Successful"]
        skipped = before - len(combos)
        use_slots_csv = False
        logger.info(
            "DoorDash: %d campaign mappings; %d already Successful, %d remaining.",
            before, skipped, len(combos),
        )
        push_to_slack(slack_msg.campaigns_resume(skipped=skipped, remaining=len(combos)))

    else:
        # --- FULL MODE: Login → Reports → Analysis → Campaigns ---
        marketing_path, financial_path, _diag = _discover_downloads(download_dir)

        if marketing_path and financial_path:
            logger.info("=" * 70)
            logger.info("PHASE 1: SKIPPED — both reports already in download dir")
            logger.info("  Financial: %s", financial_path.name)
            logger.info("  Marketing: %s", marketing_path.name)
            logger.info("=" * 70)
            push_to_slack("⏭️ Reports already downloaded — skipping Phase 1")
            await _kill_browser(browser)
            browser = None
        else:
            reports_task = get_task_description_reports_only(
                email=email,
                password=password,
                start_date=start_date,
                end_date=end_date,
                session_prepared=True,
            )

            agent = Agent(task=reports_task, llm=llm, browser=browser)

            logger.info("=" * 70)
            logger.info("PHASE 1: LOGIN + REPORTS (login, create financial & marketing, download)")
            logger.info("  Email: %s", email)
            logger.info("  Date range: %s to %s", start_date, end_date)
            logger.info("  Download dir: %s", download_dir)
            logger.info("=" * 70)
            push_to_slack(
                slack_msg.reports_phase_started(date_range=f"{start_date} → {end_date}")
            )
            phase1_start = time.time()
            try:
                await _prepare_portal_session(browser, email, password)
                await asyncio.wait_for(agent.run(), timeout=AGENT_REPORTS_TIMEOUT)
                phase1_elapsed = time.time() - phase1_start
                logger.info("Phase 1: Login + reports completed in %.0fs", phase1_elapsed)
                push_to_slack(slack_msg.portal_logged_in())
            except asyncio.TimeoutError:
                await _kill_browser(browser)
                push_to_slack(
                    slack_msg.portal_login_failed(
                        detail=f"Reports timed out after {AGENT_REPORTS_TIMEOUT}s"
                    )
                )
                raise RuntimeError(f"Phase 1 (reports) timed out after {AGENT_REPORTS_TIMEOUT}s")
            except Exception as e:
                await _kill_browser(browser)
                push_to_slack(slack_msg.portal_login_failed(detail=str(e)))
                raise e

            marketing_path, financial_path, _diag = _discover_downloads(download_dir)

            # --- Retry: if one report is missing, attempt to download just the missing one ---
            if not financial_path or not marketing_path:
                missing = []
                if not financial_path:
                    missing.append("Financial")
                if not marketing_path:
                    missing.append("Marketing")
                logger.warning("DoorDash (browser-use): Missing report(s) after Phase 1: %s. Retrying download.", ", ".join(missing))
                push_to_slack(slack_msg.report_missing_retry(names=missing))

                retry_task = _get_retry_download_task(missing)
                retry_agent = Agent(task=retry_task, llm=llm, browser=browser)
                try:
                    await asyncio.wait_for(retry_agent.run(), timeout=300)  # 5 min retry
                    marketing_path, financial_path, _diag = _discover_downloads(download_dir)
                    logger.info("DoorDash (browser-use): After retry — financial=%s, marketing=%s", financial_path, marketing_path)
                except Exception as retry_err:
                    logger.warning("DoorDash (browser-use): Retry download failed: %s", retry_err)

        if financial_path:
            logger.info("DoorDash (browser-use): Financial report at %s", financial_path)
            push_to_slack("📥 Financial report ready")
        else:
            push_to_slack("❌ Financial report missing")

        if marketing_path:
            logger.info("DoorDash (browser-use): Marketing report at %s", marketing_path)
            push_to_slack("📥 Marketing report ready")
        else:
            push_to_slack("❌ Marketing report missing")

        if financial_path and marketing_path:
            push_to_slack(slack_msg.reports_ready())

        # --- Find previous combined analysis from sibling run folders ---
        _all_combined: list[Path] = []
        _dir_name = download_dir.name
        _prefix_match = re.match(r"^(.+)-\d{8}_\d{6}$", _dir_name)
        if _prefix_match:
            _email_prefix = _prefix_match.group(1)
            for sibling in download_dir.parent.glob(f"{_email_prefix}-*"):
                if sibling == download_dir:
                    continue
                _all_combined.extend(sibling.glob("combined_analysis_*.xlsx"))
        _all_combined.extend(download_dir.glob("combined_analysis_*.xlsx"))
        old_combined_files = sorted(_all_combined, key=lambda f: f.parent.name, reverse=True)
        if old_combined_files:
            logger.info("Found previous combined analysis: %s", old_combined_files[0])

        existing_combined = sorted(
            download_dir.glob("combined_analysis_*.xlsx"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        reusable_combined = next(
            (p for p in existing_combined if _combined_has_financial_sheets(p)),
            None,
        )
        if reusable_combined:
            combined_path = reusable_combined
            logger.info("=" * 70)
            logger.info("ANALYSIS PHASE: SKIPPED — combined report already exists")
            logger.info("  %s", combined_path.name)
            logger.info("=" * 70)
            push_to_slack(f"⏭️ Analysis already done — using {combined_path.name}")
        else:
            if existing_combined:
                logger.warning(
                    "Ignoring incomplete combined analysis %s (no Day-Slot sheets) — re-running analysis",
                    existing_combined[0].name,
                )
            logger.info("=" * 70)
            logger.info("ANALYSIS PHASE: Financial + Marketing analysis, combined report, Google Sheets")
            logger.info("=" * 70)
            push_to_slack(slack_msg.analysis_started())
            analysis_start = time.time()
            combined_path = await analysis_callback(marketing_path, financial_path)
            analysis_elapsed = time.time() - analysis_start
            logger.info("Analysis phase completed in %.0fs", analysis_elapsed)

        if not combined_path or not Path(combined_path).is_file():
            logger.warning("No combined_analysis file returned — campaigns will have no slot data")
            push_to_slack(slack_msg.analysis_missing())
        elif reusable_combined:
            push_to_slack(slack_msg.analysis_ready(seconds=0))
        else:
            push_to_slack(slack_msg.analysis_ready(seconds=analysis_elapsed))

        # --- Copy Campaign Mappings from previous run if available, then run non-Successful ones ---
        combos = []
        use_slots_csv = False
        copied_from_previous = False

        if old_combined_files and combined_path and Path(combined_path).is_file():
            copied = copy_campaign_mappings_from_previous(old_combined_files[0], Path(combined_path))
            if copied:
                all_combos = read_campaign_combos_from_mappings(Path(combined_path))
                if all_combos:
                    copied_from_previous = True
                    before = len(all_combos)
                    combos = [c for c in all_combos if c.get("status") != "Successful"]
                    skipped = before - len(combos)
                    logger.info(
                        "DoorDash: Copied %d campaign mappings from previous run; %d already Successful, %d remaining.",
                        before, skipped, len(combos),
                    )
                    if skipped:
                        push_to_slack(
                            slack_msg.campaigns_resume(skipped=skipped, remaining=len(combos))
                        )

        # Fallback: build combos from Day-Slot sheets if no previous Campaign Mappings available
        if not copied_from_previous:
            if get_campaign_combos_from_slots_and_combined and slots_csv_path.is_file() and combined_path and Path(combined_path).is_file():
                combos = get_campaign_combos_from_slots_and_combined(slots_csv_path, Path(combined_path))
                if combos:
                    use_slots_csv = True
                    logger.info("DoorDash (browser-use): Found %s campaign combos from Day-Slot sheets + slots grid (one per min_subtotal per store).", len(combos))
            if not combos and combined_path and Path(combined_path).is_file() and get_all_campaign_combos_from_combined_analysis:
                combos = get_all_campaign_combos_from_combined_analysis(Path(combined_path))
                logger.info("DoorDash (browser-use): Found %s campaign combos from Day-Slot sheets (store IDs from sheets).", len(combos))

            # Push fresh campaign mappings to combined analysis sheet
            if combined_path and Path(combined_path).is_file() and combos:
                mappings = []
                for c in combos:
                    slot_tags = c.get("slot_tags")
                    if slot_tags is None and c.get("day") and c.get("slot"):
                        slot_tags = [f"{c.get('day', '')}-{c.get('slot', '')}"]
                    mappings.append({
                        "store_id": c.get("store_id", ""),
                        "store_name": c.get("store_name", ""),
                        "min_subtotal": c.get("min_subtotal", 10),
                        "slot_tags": slot_tags or [],
                        "campaign_name": c.get("campaign_name", ""),
                    })
                append_campaign_mappings_to_workbook(Path(combined_path), mappings)

    reset_task = _MARKETING_RESET_FALLBACK_TASK
    nav_to_marketing_task = _NAV_TO_MARKETING_TASK

    if combos:
        if browser is None:
            browser = _get_browser(download_dir, keep_alive=True, doordash_email=email)
            relogin_ok = await _relogin_portal_session(browser, email, password)
            if not relogin_ok:
                await _kill_browser(browser)
                raise RuntimeError("Failed to log in before campaign creation")

        if ensure_campaigns_executed_csv:
            ensure_campaigns_executed_csv(download_dir)

        total = len(combos)
        logger.info("=" * 70)
        logger.info("PHASE 2: CAMPAIGN CREATION — %s campaigns to create", total)
        logger.info("Source: %s | Browser restart every %s campaigns", "slots.csv" if use_slots_csv else "combined_analysis", MAX_CAMPAIGNS_PER_SESSION)
        logger.info("=" * 70)
        push_to_slack(slack_msg.campaigns_phase_started(product="Offers", count=total))

        # Tracking stats
        phase2_start = time.time()
        stats = {"successful": 0, "failed": 0, "skipped": 0, "timed_out": 0}
        campaign_times: list[float] = []

        for i, combo in enumerate(combos, 1):
            campaign_start = time.time()

            # --- Browser restart every N campaigns ---
            if i > 1 and (i - 1) % MAX_CAMPAIGNS_PER_SESSION == 0:
                logger.info("--- Browser restart after %d campaigns (session limit: %d) ---", i - 1, MAX_CAMPAIGNS_PER_SESSION)
                await _kill_browser(browser)
                browser = _get_browser(download_dir, keep_alive=True, doordash_email=email)
                relogin_ok = await _relogin_portal_session(browser, email, password)
                if not relogin_ok:
                    elapsed = time.time() - phase2_start
                    push_to_slack(
                        slack_msg.campaigns_aborted(
                            index=i,
                            total=total,
                            ok=stats["successful"],
                            failed=stats["failed"],
                            skipped=stats["skipped"],
                        )
                    )
                    logger.error("Re-login failed after 2 attempts; stopping campaign loop")
                    await _kill_browser(browser)
                    return

            # --- Navigation reset ---
            try:
                reset_agent = Agent(task=nav_to_marketing_task, llm=llm, browser=browser)
                await asyncio.wait_for(reset_agent.run(), timeout=AGENT_RESET_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning("[%d/%d] Nav reset timed out; trying sidebar fallback", i, total)
                try:
                    fallback_agent = Agent(task=reset_task, llm=llm, browser=browser)
                    await asyncio.wait_for(fallback_agent.run(), timeout=AGENT_RESET_TIMEOUT)
                except Exception:
                    logger.warning("[%d/%d] Sidebar fallback also failed", i, total)
            except Exception as e:
                logger.warning("[%d/%d] Nav reset failed: %s; continuing", i, total, e)

            # --- Health check every 5 campaigns (not on restart boundaries) ---
            if i > 1 and (i - 1) % MAX_CAMPAIGNS_PER_SESSION != 0 and (i - 1) % 5 == 0:
                try:
                    health_agent = Agent(
                        task=_PAGE_HEALTH_CHECK_TASK,
                        llm=llm, browser=browser,
                    )
                    health_history = await asyncio.wait_for(health_agent.run(), timeout=30)
                    health_result = ""
                    if health_history and hasattr(health_history, "final_result"):
                        val = health_history.final_result
                        health_result = str(val() if callable(val) else val) if val is not None else ""
                    if "PAGE_BLANK" in health_result.upper():
                        logger.warning("[%d/%d] Health check: page blank — restarting browser", i, total)
                        await _kill_browser(browser)
                        browser = _get_browser(download_dir, keep_alive=True, doordash_email=email)
                        await _relogin_portal_session(browser, email, password)
                        push_to_slack(slack_msg.browser_restarted(index=i, total=total))
                        reset_agent = Agent(task=nav_to_marketing_task, llm=llm, browser=browser)
                        await asyncio.wait_for(reset_agent.run(), timeout=AGENT_RESET_TIMEOUT)
                except Exception as health_err:
                    logger.debug("Health check error (non-fatal): %s", health_err)

            # --- Campaign details ---
            campaign_name = str(combo.get("campaign_name", ""))
            store_id = str(combo.get("store_id", ""))
            min_subtotal = str(combo.get("min_subtotal", "10"))
            slot_count = len(combo.get("slot_tags", []))

            # Progress calculation
            pct = (i / total) * 100
            avg_time = sum(campaign_times) / len(campaign_times) if campaign_times else 0
            eta_sec = avg_time * (total - i) if campaign_times else 0
            eta_str = f"{eta_sec/60:.0f}m" if eta_sec > 0 else "calculating..."

            logger.info(
                "[%d/%d] (%.0f%%) %s — store %s, $%s, %d slots | ETA: %s",
                i, total, pct, campaign_name, store_id, min_subtotal, slot_count, eta_str,
            )

            # --- Run campaign agent ---
            campaign_task = get_task_description_campaign_for_subtotal_combo(
                combo, include_session_preamble=False
            )
            status = "Failed"
            try:
                campaign_tools = _build_campaign_tools()
                campaign_agent = Agent(task=campaign_task, llm=llm, browser=browser, tools=campaign_tools)
                history = await asyncio.wait_for(campaign_agent.run(), timeout=AGENT_CAMPAIGN_TIMEOUT)
                completed_ok = True
                if history is not None:
                    if hasattr(history, "is_successful") and callable(history.is_successful):
                        completed_ok = history.is_successful()
                    elif hasattr(history, "final_result"):
                        val = history.final_result
                        completed_ok = bool(val() if callable(val) else val) if val is not None else False

                # Check for duplicate campaign
                final_text = ""
                if history is not None and hasattr(history, "final_result"):
                    val = history.final_result
                    final_text = str(val() if callable(val) else val) if val is not None else ""
                duplicate_phrases = [
                    "same as one of your live campaigns",
                    "duplicate",
                    "already exists",
                    "campaign are the same",
                ]
                is_duplicate = any(p in final_text.lower() for p in duplicate_phrases)

                if is_duplicate:
                    status = "Skipped (duplicate)"
                    stats["skipped"] += 1
                elif completed_ok:
                    status = "Successful"
                    stats["successful"] += 1
                else:
                    status = "Failed"
                    stats["failed"] += 1
            except asyncio.TimeoutError:
                status = "Failed"
                stats["timed_out"] += 1
                stats["failed"] += 1
            except Exception as e:
                status = "Failed"
                stats["failed"] += 1
                logger.warning("[%d/%d] %s error: %s", i, total, campaign_name, e)

            # --- Timing ---
            campaign_elapsed = time.time() - campaign_start
            campaign_times.append(campaign_elapsed)

            # --- Terminal log with result ---
            status_icon = {"Successful": "OK", "Skipped (duplicate)": "SKIP", "Failed": "FAIL"}.get(status, "FAIL")
            logger.info(
                "[%d/%d] %s %s (%.0fs) | Running: %d ok, %d fail, %d skip, %d timeout",
                i, total, status_icon, campaign_name, campaign_elapsed,
                stats["successful"], stats["failed"], stats["skipped"], stats["timed_out"],
            )

            # --- Slack: per-campaign status + periodic progress ---
            if status == "Successful":
                push_to_slack(
                    slack_msg.campaign_item_result(
                        index=i, total=total, name=campaign_name, outcome="done"
                    )
                )
            elif status == "Skipped (duplicate)":
                push_to_slack(
                    slack_msg.campaign_item_result(
                        index=i, total=total, name=campaign_name, outcome="skipped"
                    )
                )
            elif "timed_out" in str(stats.get("_last_reason", "")) or campaign_elapsed >= AGENT_CAMPAIGN_TIMEOUT - 5:
                push_to_slack(
                    slack_msg.campaign_item_result(
                        index=i, total=total, name=campaign_name, outcome="timed out"
                    )
                )
            else:
                push_to_slack(
                    slack_msg.campaign_item_result(
                        index=i, total=total, name=campaign_name, outcome="failed"
                    )
                )

            # Slack progress summary every 10 campaigns
            if i % 10 == 0 or i == total:
                push_to_slack(
                    slack_msg.campaigns_progress(
                        product="Offers",
                        index=i,
                        total=total,
                        ok=stats["successful"],
                        failed=stats["failed"],
                        skipped=stats["skipped"],
                    )
                )

            # --- Write status to tracking ---
            if combined_path and Path(combined_path).is_file():
                update_campaign_mapping_status(Path(combined_path), campaign_name, status)

            if log_campaign_executed:
                log_campaign_executed(
                    download_dir,
                    store_id=store_id,
                    campaign_name=campaign_name,
                    pct_value=15,
                    min_subtotal=float(combo.get("min_subtotal", 10)),
                    max_discount="Always lowest",
                    status=status,
                )

            await asyncio.sleep(1)

        # --- Final summary ---
        total_elapsed = time.time() - phase2_start
        success_rate = (stats["successful"] / total * 100) if total > 0 else 0
        avg_campaign = sum(campaign_times) / len(campaign_times) if campaign_times else 0

        logger.info("=" * 70)
        logger.info("PHASE 2 COMPLETE")
        logger.info("  Total:      %d campaigns in %.0f min (%.1f hrs)", total, total_elapsed / 60, total_elapsed / 3600)
        logger.info("  Successful: %d (%.0f%%)", stats["successful"], success_rate)
        logger.info("  Failed:     %d (timed out: %d)", stats["failed"], stats["timed_out"])
        logger.info("  Skipped:    %d (duplicate)", stats["skipped"])
        logger.info("  Avg time:   %.0fs per campaign", avg_campaign)
        logger.info("  Est. cost:  $%.2f (@ $0.002/step)", total * avg_campaign / 6.8 * 0.002)  # rough estimate
        logger.info("=" * 70)

        push_to_slack(
            slack_msg.campaigns_complete(
                product="Offers",
                ok=stats["successful"],
                failed=stats["failed"],
                skipped=stats["skipped"],
                minutes=total_elapsed / 60,
            )
        )

    else:
        logger.warning(
            "DoorDash (browser-use): No campaign combos from combined_analysis. "
            "Store IDs come from Day-Slot - {StoreID} sheets. Skip campaigns until combined_analysis is created."
        )

    await _kill_browser(browser)


def get_task_description_ads_campaign(
    row: dict,
    *,
    include_session_preamble: bool = True,
) -> str:
    """Sponsored listing campaign task (Advertise to all customers / Existing customers)."""
    store_id = str(row.get("store_id", "")).strip()
    store_name = str(row.get("store_name", "")).strip()
    slot_tags = row.get("slot_tags") or []
    if not isinstance(slot_tags, (list, tuple)):
        slot_tags = []
    slot_tags = [int(t) for t in slot_tags if t is not None and str(t).strip() != ""]
    tags_str = ", ".join(str(t) for t in sorted(slot_tags))
    try:
        bid = float(row.get("bid_strategy") or row.get("minimum_bid") or 3)
    except (TypeError, ValueError):
        bid = 3.0
    try:
        budget = float(row.get("budget") or 0)
    except (TypeError, ValueError):
        budget = 0.0
    campaign_name = str(row.get("campaign_name") or f"TODC-ADS-{store_id}").strip()

    selected_set = set(slot_tags)
    all_tags = set(range(1, 43))
    unselected_set = all_tags - selected_set
    _GRID_ROWS = ["Overnight", "Breakfast", "Lunch", "Afternoon", "Dinner", "Late night"]
    _GRID_COLS = ["Mon", "Tue", "Wed", "Thur", "Fri", "Sat", "Sun"]

    def _group_by_row(tag_set):
        rows = {}
        for t in sorted(tag_set):
            row_idx = (t - 1) // 7
            row_name = _GRID_ROWS[row_idx]
            col_name = _GRID_COLS[(t - 1) % 7]
            rows.setdefault(row_name, []).append((t, col_name))
        return rows

    if len(selected_set) == 42:
        manual_fallback = "All 42 cells should already be selected. Just click Save."
    elif len(unselected_set) <= 20:
        grouped = _group_by_row(unselected_set)
        lines = []
        for row_name, cells in grouped.items():
            cols = ", ".join(col for _, col in cells)
            lines.append(f"  - {row_name} row: click {cols}")
        manual_fallback = (
            f"DESELECT these {len(unselected_set)} cells (click each ONCE):\n"
            + "\n".join(lines)
            + "\n  Then click Save."
        )
    else:
        grouped = _group_by_row(selected_set)
        lines = []
        for row_name, cells in grouped.items():
            cols = ", ".join(col for _, col in cells)
            lines.append(f"  - {row_name} row: click {cols}")
        manual_fallback = (
            f"Click Weekdays ONCE, then Weekends ONCE (grid now empty). "
            f"Then SELECT these {len(selected_set)} cells (click each ONCE):\n"
            + "\n".join(lines)
            + "\n  Then click Save. NEVER click Weekdays/Weekends again."
        )

    schedule_instructions = f"""- IMPORTANT: Use the set_schedule_grid action to configure the grid automatically.
- Call: set_schedule_grid(wanted_tags="{tags_str}")
- Do NOT manually click grid cells. If set_schedule_grid returns SUCCESS, proceed to STEP 7.
- If set_schedule_grid returns ERROR twice, do it manually: {manual_fallback}"""

    session_email = str(row.get("doordash_email") or os.getenv("DOORDASH_EMAIL", "")).strip()
    session_password = str(row.get("doordash_password") or os.getenv("DOORDASH_PASSWORD", "")).strip()
    preamble_block = ""
    if include_session_preamble:
        from shared.doordash_portal_tasks import build_campaign_session_preamble

        preamble_block = build_campaign_session_preamble(session_email, session_password or None) + "\n"

    budget_step = (
        f"- Click Edit next to budget. Set weekly budget to ${budget:.2f}. Click Save."
        if budget > 0
        else "- If budget is shown, leave default or set a reasonable weekly budget. Click Save."
    )

    return f"""
ROLE: You are automating sponsored listing campaign creation on DoorDash Merchant Portal. You are already logged in.

{preamble_block}RULES:
- Do NOT create or download reports.
- Use "Advertise to all customers" (sponsored listing), NOT discount promotion cards.

CAMPAIGN: {campaign_name} | STORE: {store_id} ({store_name or "N/A"}) | BID: ${bid:g} | TAGS: {tags_str}

STEP 1 — Open campaign builder:
- Click "Marketing" in the left sidebar. Wait for page to load.
- Click "Run a campaign". Wait for campaign type cards.
- Find "Advertise to all customers" and click "Select".
- Click "Customize your campaign". Wait for form to load.

STEP 2 — Select store:
- Click Edit (pencil) next to "Stores". Wait for modal.
- Click "Select All" to deselect all stores.
- Search "{store_id}" in search bar. If not found, search "{store_name}" instead.
- Select ONLY the one matching store. Click "Save".

STEP 3 — Audience:
- Click Edit next to audience / customer targeting.
- Select "Existing customers".
- Click "Save".

STEP 4 — Bid:
- Click Edit next to bid / cost per order / minimum bid.
- Set minimum bid to ${bid:g}.
- Click "Save".

STEP 5 — Budget:
{budget_step}

STEP 6 — Schedule:
- Click Edit next to "Scheduling". Wait for modal with grid.
- Click "Set a custom schedule". Wait for grid.
{schedule_instructions}

STEP 7 — Campaign name:
- Click Edit next to "Campaign name". Triple-click input, type exactly: {campaign_name}
- Click "Save". WAIT until modal closes.

STEP 8 — Create:
- Confirm store, bid, schedule, and name "{campaign_name}" in the summary.
- Click the button to create/launch the sponsored listing campaign. Wait for success.
- If you see a duplicate/live-campaign warning, use done immediately and say DUPLICATE.

DONE: Use done action. Say: "{campaign_name}" created for store {store_id}.
"""


async def _login_for_campaigns(browser, llm, email: str, password: str) -> None:
    """Programmatic logout → credential login before campaign tasks."""
    await _prepare_portal_session(browser, email, password)
    logger.info("Login successful for campaign-only run")
    push_to_slack(slack_msg.portal_logged_in())


async def _run_campaign_items(
    *,
    download_dir: Path,
    email: str,
    password: str,
    items: list[dict],
    task_builder: Callable[[dict], str],
    label: str,
    use_offer_tools: bool = True,
    campaigns_workbook: Path | str | None = None,
    slot_info_csv: Path | str | None = None,
    campaign_kind: str = "offers",
) -> dict[str, Any]:
    """Login once, then create campaigns from pre-built row/combo dicts."""
    from browser_use import Agent

    if not items:
        return {"status": "success", "total": 0, "successful": 0, "failed": 0, "skipped": 0}

    download_dir = Path(download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    llm = _get_llm()
    browser = _get_browser(download_dir, keep_alive=True, doordash_email=email)

    reset_task = _MARKETING_RESET_FALLBACK_TASK
    nav_to_marketing_task = _NAV_TO_MARKETING_TASK

    try:
        push_to_slack(slack_msg.campaigns_starting(product=label, count=len(items)))
        await _login_for_campaigns(browser, llm, email, password)

        total = len(items)
        stats = {"successful": 0, "failed": 0, "skipped": 0, "timed_out": 0}
        aborted = False
        campaign_times: list[float] = []
        phase_start = time.time()

        logger.info("=" * 70)
        logger.info("CAMPAIGN CREATION — %s %s items", label, total)
        logger.info("  Browser restart every %s campaigns", MAX_CAMPAIGNS_PER_SESSION)
        logger.info("=" * 70)
        push_to_slack(slack_msg.campaigns_phase_started(product=label, count=total))

        for i, item in enumerate(items, 1):
            campaign_start = time.time()

            if i > 1 and (i - 1) % MAX_CAMPAIGNS_PER_SESSION == 0:
                logger.info(
                    "--- Browser restart after %d campaigns (session limit: %d) ---",
                    i - 1,
                    MAX_CAMPAIGNS_PER_SESSION,
                )
                await _kill_browser(browser)
                browser = _get_browser(download_dir, keep_alive=True, doordash_email=email)
                relogin_ok = await _relogin_portal_session(browser, email, password)
                if not relogin_ok:
                    push_to_slack(
                        slack_msg.campaigns_aborted(
                            index=i,
                            total=total,
                            ok=stats["successful"],
                            failed=stats["failed"],
                            skipped=stats["skipped"],
                        )
                    )
                    logger.error("Re-login failed after 2 attempts; stopping campaign loop")
                    aborted = True
                    break

            try:
                reset_agent = Agent(task=nav_to_marketing_task, llm=llm, browser=browser)
                await asyncio.wait_for(reset_agent.run(), timeout=AGENT_RESET_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning("[%d/%d] Nav reset timed out; trying sidebar fallback", i, total)
                try:
                    fallback_agent = Agent(task=reset_task, llm=llm, browser=browser)
                    await asyncio.wait_for(fallback_agent.run(), timeout=AGENT_RESET_TIMEOUT)
                except Exception:
                    logger.warning("[%d/%d] Sidebar fallback also failed", i, total)
            except Exception as e:
                logger.warning("[%d/%d] Nav reset failed: %s; continuing", i, total, e)

            if i > 1 and (i - 1) % MAX_CAMPAIGNS_PER_SESSION != 0 and (i - 1) % 5 == 0:
                try:
                    health_agent = Agent(
                        task=_PAGE_HEALTH_CHECK_TASK,
                        llm=llm,
                        browser=browser,
                    )
                    health_history = await asyncio.wait_for(health_agent.run(), timeout=30)
                    health_result = ""
                    if health_history and hasattr(health_history, "final_result"):
                        val = health_history.final_result
                        health_result = str(val() if callable(val) else val) if val is not None else ""
                    if "PAGE_BLANK" in health_result.upper():
                        logger.warning("[%d/%d] Health check: page blank — restarting browser", i, total)
                        await _kill_browser(browser)
                        browser = _get_browser(download_dir, keep_alive=True, doordash_email=email)
                        await _relogin_portal_session(browser, email, password)
                        push_to_slack(slack_msg.browser_restarted(index=i, total=total))
                        reset_agent = Agent(task=nav_to_marketing_task, llm=llm, browser=browser)
                        await asyncio.wait_for(reset_agent.run(), timeout=AGENT_RESET_TIMEOUT)
                except Exception as health_err:
                    logger.debug("Health check error (non-fatal): %s", health_err)

            campaign_name = str(item.get("campaign_name", ""))
            store_id = str(item.get("store_id", ""))
            min_subtotal = str(item.get("min_subtotal", ""))
            slot_count = len(item.get("slot_tags") or [])
            pct = (i / total) * 100
            avg_time = sum(campaign_times) / len(campaign_times) if campaign_times else 0
            eta_sec = avg_time * (total - i) if campaign_times else 0
            eta_str = f"{eta_sec/60:.0f}m" if eta_sec > 0 else "calculating..."
            logger.info(
                "[%d/%d] (%.0f%%) %s — store %s, $%s, %d slots | ETA: %s",
                i,
                total,
                pct,
                campaign_name,
                store_id,
                min_subtotal,
                slot_count,
                eta_str,
            )

            status = "Failed"
            try:
                campaign_task = task_builder(item)
                tools = _build_campaign_tools() if use_offer_tools else _build_campaign_tools()
                campaign_agent = Agent(task=campaign_task, llm=llm, browser=browser, tools=tools)
                history = await asyncio.wait_for(campaign_agent.run(), timeout=AGENT_CAMPAIGN_TIMEOUT)
                completed_ok = True
                if history is not None:
                    if hasattr(history, "is_successful") and callable(history.is_successful):
                        completed_ok = history.is_successful()
                    elif hasattr(history, "final_result"):
                        val = history.final_result
                        completed_ok = bool(val() if callable(val) else val) if val is not None else False
                final_text = ""
                if history is not None and hasattr(history, "final_result"):
                    val = history.final_result
                    final_text = str(val() if callable(val) else val) if val is not None else ""
                is_duplicate = any(
                    p in final_text.lower()
                    for p in (
                        "same as one of your live campaigns",
                        "duplicate",
                        "already exists",
                        "campaign are the same",
                    )
                )
                if is_duplicate:
                    status = "Skipped (duplicate)"
                    stats["skipped"] += 1
                    slot_tags = item.get("slot_tags") or []
                    logger.warning(
                        "[%d/%d] %s duplicate on portal — intended slot_tags=%s",
                        i,
                        total,
                        campaign_name,
                        slot_tags,
                    )
                elif completed_ok:
                    status = "Successful"
                    stats["successful"] += 1
                else:
                    status = "Failed"
                    stats["failed"] += 1
            except asyncio.TimeoutError:
                status = "Failed"
                stats["timed_out"] += 1
                stats["failed"] += 1
            except Exception as e:
                status = "Failed"
                stats["failed"] += 1
                logger.warning("[%d/%d] %s error: %s", i, total, campaign_name, e)

            campaign_elapsed = time.time() - campaign_start
            campaign_times.append(campaign_elapsed)
            item["status"] = status
            logger.info("[%d/%d] %s %s (%.0fs)", i, total, status, campaign_name, campaign_elapsed)

            if campaigns_workbook:
                try:
                    from shared.strategist_campaign_sheets import write_strategist_campaign_statuses

                    write_strategist_campaign_statuses(
                        campaigns_workbook,
                        slot_info_csv,
                        item,
                        status,
                        kind="ads" if campaign_kind == "ads" else "offers",
                    )
                except Exception as exc:
                    logger.warning(
                        "[%d/%d] Strategist status writeback failed for %s: %s",
                        i,
                        total,
                        campaign_name,
                        exc,
                    )

            if status == "Successful":
                push_to_slack(
                    slack_msg.campaign_item_result(
                        index=i, total=total, name=campaign_name, outcome="done"
                    )
                )
            elif status == "Skipped (duplicate)":
                push_to_slack(
                    slack_msg.campaign_item_result(
                        index=i, total=total, name=campaign_name, outcome="skipped"
                    )
                )
            else:
                push_to_slack(
                    slack_msg.campaign_item_result(
                        index=i, total=total, name=campaign_name, outcome="failed"
                    )
                )

            if i % 10 == 0 or i == total:
                push_to_slack(
                    slack_msg.campaigns_progress(
                        product=label,
                        index=i,
                        total=total,
                        ok=stats["successful"],
                        failed=stats["failed"],
                        skipped=stats["skipped"],
                    )
                )

            await asyncio.sleep(1)

        total_elapsed = time.time() - phase_start
        push_to_slack(
            slack_msg.campaigns_complete(
                product=label,
                ok=stats["successful"],
                failed=stats["failed"],
                skipped=stats["skipped"],
                minutes=total_elapsed / 60,
            )
        )
        if stats["failed"] == 0 and not aborted:
            run_status = "success"
        elif stats["successful"] > 0:
            run_status = "partial"
        else:
            run_status = "failed"
        return {
            "status": run_status,
            "total": total,
            "successful": stats["successful"],
            "failed": stats["failed"],
            "skipped": stats["skipped"],
            "timed_out": stats["timed_out"],
            "unattempted": total - stats["successful"] - stats["failed"] - stats["skipped"] - stats["timed_out"],
            "elapsed_seconds": total_elapsed,
            "download_dir": str(download_dir),
        }
    finally:
        await _kill_browser(browser)


async def run_offers_campaigns_from_combos(
    *,
    download_dir: Path,
    email: str,
    password: str,
    combos: list[dict],
    campaigns_workbook: Path | str | None = None,
    slot_info_csv: Path | str | None = None,
) -> dict[str, Any]:
    """Create discount/promo campaigns from Strategist Offers rows (combo dicts)."""
    enriched = []
    for c in combos:
        row = dict(c)
        row.setdefault("doordash_email", email)
        row.setdefault("doordash_password", password)
        enriched.append(row)
    return await _run_campaign_items(
        download_dir=download_dir,
        email=email,
        password=password,
        items=enriched,
        task_builder=lambda item: get_task_description_campaign_for_subtotal_combo(
            item, include_session_preamble=False
        ),
        label="Offers",
        use_offer_tools=True,
        campaigns_workbook=campaigns_workbook,
        slot_info_csv=slot_info_csv,
        campaign_kind="offers",
    )


async def run_ads_campaigns_from_rows(
    *,
    download_dir: Path,
    email: str,
    password: str,
    rows: list[dict],
    campaigns_workbook: Path | str | None = None,
    slot_info_csv: Path | str | None = None,
) -> dict[str, Any]:
    """Create sponsored listing campaigns from Strategist Ads rows."""
    enriched = []
    for r in rows:
        row = dict(r)
        row.setdefault("doordash_email", email)
        row.setdefault("doordash_password", password)
        enriched.append(row)
    return await _run_campaign_items(
        download_dir=download_dir,
        email=email,
        password=password,
        items=enriched,
        task_builder=lambda item: get_task_description_ads_campaign(
            item, include_session_preamble=False
        ),
        label="Ads",
        use_offer_tools=True,
        campaigns_workbook=campaigns_workbook,
        slot_info_csv=slot_info_csv,
        campaign_kind="ads",
    )


async def run_ads_campaigns_from_sheet(
    *,
    download_dir: Path,
    email: str,
    password: str,
    sheet_path: Path,
) -> dict[str, Any]:
    """Create sponsored listings from a CSV/Excel Ads sheet (upload or Strategist export)."""
    from shared.strategist_campaign_sheets import load_ads_rows_from_path

    rows = load_ads_rows_from_path(Path(sheet_path))
    return await run_ads_campaigns_from_rows(
        download_dir=download_dir,
        email=email,
        password=password,
        rows=rows,
    )
