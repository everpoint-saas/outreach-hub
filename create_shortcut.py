
import os
import sys
import subprocess

def create_shortcut():
    # Paths
    cwd = os.path.dirname(os.path.abspath(__file__))
    target = sys.executable  # python.exe
    script = os.path.join(cwd, "main.py")

    # Name of the shortcut
    lnk_name = "MailingList_Start.lnk"
    lnk_path = os.path.join(cwd, lnk_name)

    # VBScript to create the shortcut
    # We explicitly set WorkingDirectory so it works from Desktop
    vbs_content = f"""
    Set oWS = WScript.CreateObject("WScript.Shell")
    sLinkFile = "{lnk_path}"
    Set oLink = oWS.CreateShortcut(sLinkFile)
    oLink.TargetPath = "{target}"
    oLink.Arguments = "{script.replace(os.sep, os.sep)}"
    oLink.WorkingDirectory = "{cwd}"
    oLink.Description = "Run Mailing List App"
    oLink.IconLocation = "{target},0"
    oLink.Save
    """

    vbs_path = os.path.join(cwd, "create_shortcut.vbs")

    try:
        with open(vbs_path, "w", encoding="utf-8") as f:
            f.write(vbs_content)

        subprocess.run(["cscript", "//Nologo", vbs_path], check=True)
        print(f"Shortcut created: {lnk_path}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if os.path.exists(vbs_path):
            os.remove(vbs_path)

if __name__ == "__main__":
    create_shortcut()
