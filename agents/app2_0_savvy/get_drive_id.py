"""
Simple script to get the Shared Drive ID.
Run this to find your Shared Drive ID for debugging purposes.
"""
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

def get_shared_drive_id(drive_name="Data-Analysis-Uploads", credentials_path=None):
    """
    Get the Shared Drive ID by name.
    
    Args:
        drive_name: Name of the shared drive
        credentials_path: Path to service account JSON file
    
    Returns:
        Shared Drive ID
    """
    if credentials_path is None:
        app_dir = Path(__file__).parent
        credentials_path = app_dir / "todc-marketing-ad02212d4f16.json"
    
    credentials_path = Path(credentials_path)
    
    if not credentials_path.exists():
        print(f"❌ Service account credentials not found at: {credentials_path}")
        return None
    
    try:
        # Authenticate
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=credentials)
        
        # List all shared drives
        print(f"🔍 Searching for shared drive: '{drive_name}'...")
        results = service.drives().list(pageSize=100).execute()
        
        drives = results.get('drives', [])
        
        if not drives:
            print("❌ No shared drives found. Make sure the service account has access to shared drives.")
            return None
        
        print(f"\n📋 Found {len(drives)} shared drive(s):")
        print("-" * 60)
        
        # Find the drive by name
        for drive in drives:
            print(f"  Name: {drive['name']}")
            print(f"  ID:   {drive['id']}")
            print(f"  Kind: {drive.get('kind', 'N/A')}")
            print("-" * 60)
            
            if drive['name'] == drive_name:
                print(f"\n✅ Found matching drive!")
                print(f"   Drive Name: {drive['name']}")
                print(f"   Drive ID:   {drive['id']}")
                return drive['id']
        
        print(f"\n⚠️  Shared drive '{drive_name}' not found in the list above.")
        print("   Please check:")
        print("   1. The drive name is correct")
        print("   2. The service account has access to the shared drive")
        print("   3. The service account has the 'Drive API' enabled")
        
        return None
        
    except HttpError as error:
        print(f"❌ Error accessing Google Drive API: {error}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("Google Drive Shared Drive ID Finder")
    print("=" * 60)
    print()
    
    drive_id = get_shared_drive_id()
    
    if drive_id:
        print()
        print("=" * 60)
        print(f"Your Shared Drive ID: {drive_id}")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("Could not retrieve Shared Drive ID")
        print("=" * 60)
