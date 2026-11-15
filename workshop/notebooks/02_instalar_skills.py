# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · Instalar las skills para Genie Code (sin CLI)
# MAGIC
# MAGIC Copia `navidad-hack-infra` y `navidad-hack-build-assistant` a tu carpeta de skills de Genie Code
# MAGIC (`/Workspace/Users/<tú>/.assistant/skills/`). Después, en Genie Code: *«Ayúdame a construir sobre el Taller de Navidad»*.

# COMMAND ----------

import shutil
from pathlib import Path

from databricks.sdk import WorkspaceClient

nb_path = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
repo = Path("/Workspace" + nb_path).parents[2]
me = dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()
dest = Path(f"/Workspace/Users/{me}/.assistant/skills")
dest.mkdir(parents=True, exist_ok=True)
skip = shutil.ignore_patterns("tests", "tools", "__pycache__", ".pytest_cache", "copied-apps")
for skill in ("navidad-hack-infra", "navidad-hack-build-assistant"):
    target = dest / skill
    if target.exists():
        # shutil.rmtree on /Workspace fails with «Directory not empty» on a re-install: delete through the
        # Workspace API (recursive, server-side). The /Workspace view can lag a few seconds, so copy with
        # dirs_exist_ok instead of waiting for the folder to disappear.
        WorkspaceClient().workspace.delete(str(target)[len("/Workspace"):], recursive=True)
    shutil.copytree(repo / skill, target, ignore=skip, dirs_exist_ok=True)
    print("instalada:", target)
