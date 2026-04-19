from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/legal", tags=["legal"])

_PRIVACY_POLICY = """\
Lumen Privacy Policy — Last updated: 2026-04-19

Data we collect:
- Your journal entries (title, body, metadata)
- Your email address and hashed password for authentication
- Your IP address in server logs (retained 30 days)

How we use your data:
- To provide the journaling service
- To sync your entries to your personal AWS S3 bucket (if enabled)
- We do not sell, share, or use your data for advertising

Your rights:
- Delete your account and all entries: Settings → Account → Delete Account
- Export your data: Settings → Export
- Data is stored in ap-south-1 only

Contact: support@lumen.app
"""

_TERMS_OF_USE = """\
Lumen Terms of Use — Last updated: 2026-04-19

- Lumen is provided as-is. No uptime guarantees are made.
- You own your journal entries. We do not claim any rights to them.
- Do not use Lumen to store illegal content.
- Accounts inactive for 12 months may be purged with 30 days notice.
"""


@router.get("/privacy", response_class=PlainTextResponse)
async def privacy_policy():
    return _PRIVACY_POLICY


@router.get("/terms", response_class=PlainTextResponse)
async def terms_of_use():
    return _TERMS_OF_USE
