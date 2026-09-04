import runpy
from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    runpy.run_module("Interface.main", run_name="__main__")
