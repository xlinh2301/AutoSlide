"""AutoSlide application entry point."""

from autoslide.api import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("autoslide.main:app", host="127.0.0.1", port=8000, reload=False)
