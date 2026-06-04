"""SuperApp Streamlit export hub.

Use this companion app when exports need server-side Google Drive credentials.
The React app creates the workbook; this app uploads that workbook either as
raw Excel or as a native Google Sheet.
"""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from gdrive_utils import describe_drive, get_drive_manager


st.set_page_config(
    page_title="SuperApp Export Hub",
    page_icon="📊",
    layout="centered",
)


st.title("SuperApp Export Hub")
st.caption("Google Drive connectivity helper for SuperApp.")

with st.expander("Credential setup", expanded=False):
    st.markdown(
        """
        Credentials are loaded in the same style as App2.0:

        - Streamlit secrets: `[gcp.service_account]`
        - Environment: `GCP_SERVICE_ACCOUNT_JSON`
        - Local file: `streamlit_app/todc-marketing-ad02212d4f16.json` (or any `todc-marketing-*.json` in that folder)

        The service account must have access to the selected Shared Drive.
        """
    )

shared_drive_name = st.text_input(
    "Shared Drive name",
    value="Data-Analysis-Uploads",
    help="This matches App2.0's default shared drive.",
)
subfolder_name = st.text_input(
    "Drive folder prefix",
    value="outputs",
    help="Files go into a flat folder like outputs_2026-05-26.",
)

test_col, clear_col = st.columns([1, 1])
with test_col:
    if st.button("Test Google Drive access", use_container_width=True):
        try:
            info = describe_drive(shared_drive_name)
            st.success(f"Connected to {info['drive_name']}")
            st.code(info["drive_id"])
        except Exception as exc:
            err = str(exc)
            if "No secrets found" in err:
                st.error(
                    "Streamlit has no secrets.toml (that message is normal locally). "
                    "Credentials should still load from `streamlit_app/todc-marketing-*.json` "
                    "after the latest fix — click **Reset cached Drive client**, then test again.\n\n"
                    f"Details: {err}"
                )
            else:
                st.error(err)
with clear_col:
    if st.button("Reset cached Drive client", use_container_width=True):
        st.cache_resource.clear()
        st.info("Drive client cache cleared.")

st.info(
    "Export is now one-click from the React dashboard. "
    "Use the Export button there; this page is only for Drive connection checks."
)
st.caption(f"Current timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
