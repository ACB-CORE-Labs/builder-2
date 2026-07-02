import json
import subprocess
import sys
import urllib.error
import urllib.request


def _get_google_project_id() -> str:
    res = subprocess.run(["gcloud", "config", "get-value", "project"], capture_output=True, text=True, check=False)
    return res.stdout.strip()


def _get_google_access_token() -> str:
    res = subprocess.run(["gcloud", "auth", "print-access-token"], capture_output=True, text=True, check=False)
    return res.stdout.strip()


def verify_google_ultra():
    print("Fetching Google Project ID...")
    project_id = _get_google_project_id()
    if not project_id:
        print("Failed to get Google Project ID from gcloud.")
        sys.exit(1)
    print(f"Project ID: {project_id}")

    print("Fetching Google Access Token...")
    access_token = _get_google_access_token()
    if not access_token:
        print("Failed to get Google Access Token from gcloud.")
        sys.exit(1)
    print("Access token retrieved successfully.")

    # We use the Vertex AI OpenAI-compatible endpoint
    # Note: Vertex AI OpenAI base is:
    # https://aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/global/endpoints/openapi
    url = f"https://aiplatform.googleapis.com/v1beta1/projects/{project_id}/locations/global/endpoints/openapi/chat/completions"

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    # Request gemini-3.5-flash explicitly
    data = {
        "model": "google/gemini-3.5-flash",
        "messages": [{"role": "user", "content": "What is 2+2? Reply only with the number."}],
    }

    print(f"\nSending test completion to {url}")
    print("Model: google/gemini-3.5-flash\n")

    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            status = response.status
            body = response.read().decode("utf-8")
            if status == 200:
                print("SUCCESS! Received 200 OK.")
                resp_json = json.loads(body)
                content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"Model Response: {content.strip()}")
            else:
                print(f"Unexpected status: {status}")
                print(f"Body: {body}")
                sys.exit(1)
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} {e.reason}")
        print(f"Body: {e.read().decode('utf-8')}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"URLError: {e.reason}")
        sys.exit(1)


if __name__ == "__main__":
    verify_google_ultra()
