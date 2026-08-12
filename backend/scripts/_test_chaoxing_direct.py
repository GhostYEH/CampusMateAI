import asyncio
import sys
import traceback

sys.path.insert(0, "F:/demo1/backend")

from app.services.chaoxing.ChaoxingClient import ChaoxingClient


async def main():
    client = ChaoxingClient()
    try:
        success, msg = await client.login("17597816673", "yaoenhua888")
        print(f"success={success}, msg={msg}")
        if success:
            cookies = {c.name: c.value for c in client.client.cookies}
            print(f"cookie_count={len(cookies)}")
            print(f"cookie_keys={list(cookies.keys())}")
            success2, result = await client.get_courses()
            print(f"get_courses success={success2}")
            if success2:
                print(f"course_count={len(result)}")
                for c in result[:5]:
                    print(f"  - {c}")
            else:
                print(f"get_courses error={result}")
    except Exception:
        traceback.print_exc()
    finally:
        await client.client.aclose()


asyncio.run(main())