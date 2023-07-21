from pathlib import Path

import httpx
from requests_toolbelt import MultipartEncoder


def post_discovery() -> httpx.Response:
    assets_dir = Path(__file__).parent / "assets"
    event_log_path = assets_dir / "AcademicCredentials_train.csv"

    data = MultipartEncoder(
        fields={
            "event_log": ("event_log.csv", event_log_path.open("rb"), "text/csv"),
        }
    )

    return httpx.post(
        "http://localhost:8000/api/v1/discoveries/",
        headers={"Content-Type": data.content_type},
        content=data.to_string(),
    )


if __name__ == "__main__":
    response = post_discovery()
    print(f"Status code: {response.status_code}, headers: {response.headers}")
    print(response.json())
