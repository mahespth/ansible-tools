import typer
from .app import AAPTui

app = typer.Typer()

@app.command(help="Open a Job Detail screen and follow logs.")
def job(job_id: int, base: str = typer.Option(...), token: str = typer.Option(...)):
    ui = AAPTui(base_url=base, token=token)
    ui.call_after_refresh(lambda: ui.open_job_detail(job_id))
    ui.run()

def main():
    app()

if __name__ == "__main__":
    main()
