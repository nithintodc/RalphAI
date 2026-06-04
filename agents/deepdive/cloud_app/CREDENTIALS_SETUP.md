# Google Drive Credentials Setup Guide

This guide explains how to add Google Drive service account credentials to enable file uploads to Google Drive.

## 📍 Where to Add Credentials

**Location:** Place the credentials file in the `app/` folder

**File Name:** `todc-marketing-ad02212d4f16.json` (or any file matching pattern `todc-marketing-*.json`)

**Full Path:** `/Users/nithi/Downloads/TODC/App2.0-cloud-app/app/todc-marketing-ad02212d4f16.json`

## 🔑 Step-by-Step: Getting Google Drive Credentials

### Step 1: Create Google Cloud Project (if needed)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable **Google Drive API**:
   - Go to **APIs & Services** → **Library**
   - Search for "Google Drive API"
   - Click **Enable**

### Step 2: Create Service Account

1. Go to **IAM & Admin** → **Service Accounts**
2. Click **"Create Service Account"**
3. Fill in details:
   - **Service account name**: `streamlit-drive-uploader` (or any name)
   - **Service account ID**: Auto-generated
   - **Description**: "Service account for Streamlit app Google Drive uploads"
4. Click **"Create and Continue"**

### Step 3: Grant Permissions

1. **Grant this service account access to project**:
   - Role: **Editor** (or more specific roles if preferred)
   - Click **"Continue"**
2. **Grant users access to this service account** (optional):
   - Skip this step
   - Click **"Done"**

### Step 4: Create and Download JSON Key

1. Click on the service account you just created
2. Go to **"Keys"** tab
3. Click **"Add Key"** → **"Create new key"**
4. Select **JSON** format
5. Click **"Create"**
6. **IMPORTANT**: The JSON file will download automatically
   - Save this file securely
   - You won't be able to download it again

### Step 5: Share Google Drive with Service Account

1. Open the downloaded JSON file
2. Find the `client_email` field (looks like: `your-service-account@project-id.iam.gserviceaccount.com`)
3. Copy this email address
4. Go to your Google Drive
5. Find or create the shared drive: **"Data-Analysis-Uploads"**
6. Right-click on the drive → **"Share"**
7. Paste the service account email
8. Grant role: **"Content Manager"** or **"Editor"**
9. Click **"Send"** (uncheck "Notify people" if you don't want an email)

### Step 6: Place Credentials File

1. Rename the downloaded JSON file to: `todc-marketing-ad02212d4f16.json`
   - Or keep the original name if it matches `todc-marketing-*.json` pattern
2. Copy the file to your app folder:
   ```bash
   # For local development
   cp /path/to/downloaded-file.json /Users/nithi/Downloads/TODC/App2.0-cloud-app/app/todc-marketing-ad02212d4f16.json
   ```
3. Verify the file is in the correct location:
   ```bash
   ls -la /Users/nithi/Downloads/TODC/App2.0-cloud-app/app/todc-marketing-*.json
   ```

## 📁 File Structure

Your app folder should look like this:

```
app/
├── app.py
├── config.py
├── todc-marketing-ad02212d4f16.json  ← Credentials file here
├── requirements.txt
└── ... (other files)
```

## ✅ Verify Credentials Are Working

### Local Testing

1. Run your Streamlit app:
   ```bash
   cd app
   streamlit run app.py
   ```

2. Try exporting data:
   - Go to Dashboard
   - Click "Export All Tables to Excel"
   - If credentials are correct, you'll see: "File uploaded to Google Drive"
   - If incorrect, you'll see: "Google Drive not initialized"

### Check Credentials File

The JSON file should contain:
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "your-service-account@project-id.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  ...
}
```

## 🚀 For Production (GCP VM)

### Option 1: Upload via SSH

1. SSH into your VM:
   ```bash
   gcloud compute ssh todc-ent-applications --zone=us-west2-a
   ```

2. Upload the file:
   ```bash
   # From your local machine
   gcloud compute scp todc-marketing-ad02212d4f16.json todc-ent-applications:/opt/streamlit-app/app/ --zone=us-west2-a
   ```

### Option 2: Add to GitHub Secrets (for CI/CD)

**Note:** This is for the GitHub Actions service account, NOT the Google Drive credentials.

The Google Drive credentials should be uploaded directly to the VM (Option 1).

## 🔒 Security Best Practices

1. ✅ **Never commit credentials to Git**
   - The file is already in `.gitignore`
   - Verify with: `git status` (should NOT show the JSON file)

2. ✅ **Use environment variables** (Alternative method)
   - You can set credentials via environment variables
   - See "Alternative: Environment Variables" section below

3. ✅ **Restrict service account permissions**
   - Only grant necessary permissions
   - Use least privilege principle

4. ✅ **Rotate credentials periodically**
   - Create new keys and replace old ones
   - Delete old keys from Google Cloud Console

## 🔄 Alternative: Environment Variables

If you prefer using environment variables instead of a file:

1. Set environment variable:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/credentials.json"
   ```

2. Or modify `gdrive_utils.py` to read from environment:
   ```python
   import os
   credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
   ```

## ❌ Troubleshooting

### Error: "Service account credentials not found"

**Solution:**
- Verify file exists: `ls app/todc-marketing-*.json`
- Check file name matches pattern: `todc-marketing-*.json`
- Verify file is in the `app/` folder (not parent directory)

### Error: "Shared drive 'Data-Analysis-Uploads' not found"

**Solution:**
1. Verify shared drive exists in Google Drive
2. Check service account email has access to the drive
3. Ensure service account has "Content Manager" or "Editor" role

### Error: "Permission denied" or "Access denied"

**Solution:**
1. Check service account has Google Drive API enabled
2. Verify service account has access to the shared drive
3. Check the service account email is correct in the JSON file

### Error: "Invalid credentials"

**Solution:**
1. Verify JSON file is not corrupted
2. Check file is valid JSON format
3. Ensure you downloaded the correct key (JSON format, not P12)

## 📝 Quick Reference

| Item | Value |
|------|-------|
| **File Location** | `app/todc-marketing-ad02212d4f16.json` |
| **File Pattern** | `todc-marketing-*.json` |
| **Required API** | Google Drive API |
| **Shared Drive** | "Data-Analysis-Uploads" |
| **Service Account Role** | Content Manager or Editor |
| **Git Status** | Should be ignored (in .gitignore) |

## 🎯 Summary

1. **Get credentials** from Google Cloud Console (Service Account → Keys → Create JSON key)
2. **Share Google Drive** with the service account email
3. **Place file** in `app/` folder as `todc-marketing-ad02212d4f16.json`
4. **Verify** it works by testing export functionality
5. **Never commit** the file to Git (already in .gitignore)

That's it! Your app will now be able to upload files to Google Drive.
