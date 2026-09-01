import httpx


class GitHubService:

    BASE_URL = "https://api.github.com"

    #gets the live pull request after getting data from webhook
    async def get_pull_request(
            self,
            owner: str,
            repo: str,
            pull_number: int
    ):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "Accept": "application/vnd.github+json"
                }
            )

        response.raise_for_status()
        return response.json()

   #get all the pull requests till now
    async def get_pull_requests(
            self,
            owner: str,
            repo: str,
            state: str = "all"
    ):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls"

        params = {
            "state": state,
            "per_page": 100
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers={
                    "Accept": "application/vnd.github+json"
                }
            )

        response.raise_for_status()
        return response.json()

    #gets the Repo data
    async def get_repository(self, owner: str, repo: str):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    #gets the repo commit sha
    async def get_branch(
            self,
            owner: str,
            repo: str,
            branch: str
    ):
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/branches/{branch}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={
                    "Accept": "application/vnd.github+json"
                }
            )

        response.raise_for_status()

        return response.json()

    # gets the changes made in a pull request
    async def get_pull_request_diff(
        self,
        owner: str,
        repo: str,
        pull_number: int
    ):
        url = (
            f"{self.BASE_URL}/repos/"
            f"{owner}/{repo}/pulls/{pull_number}"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={
                    "Accept": "application/vnd.github.v3.diff"
                }
            )

        response.raise_for_status()

        return response.text

        # gets the files changed in a pull request
    async def get_pull_request_files(
        self,
        owner: str,
        repo: str,
        pull_number: int
    ):
        url = (
            f"{self.BASE_URL}/repos/"
            f"{owner}/{repo}/pulls/{pull_number}/files"
        )

        params = {
            "per_page": 100
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                params=params,
                headers={
                    "Accept": "application/vnd.github+json"
                }
            )

        response.raise_for_status()

        return response.json()