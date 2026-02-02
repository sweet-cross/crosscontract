import shutil
from pathlib import Path


# This function name is specific to MkDocs Hooks
def on_config(config, **kwargs):
    source_dir = Path("notebooks")
    target_dir = Path("docs/notebooks")

    # Ensure target exists
    target_dir.mkdir(parents=True, exist_ok=True)

    for notebook in source_dir.glob("*.ipynb"):
        dest_file = target_dir / notebook.name
        # Only copy if file changed or doesn't exist to keep 'serve' fast
        if (
            not dest_file.exists()
            or notebook.stat().st_mtime > dest_file.stat().st_mtime
        ):
            print(f"Hook: Copying {notebook} to {target_dir}")
            shutil.copy2(notebook, dest_file)
