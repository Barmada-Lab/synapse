import os

# patch environment variables to prevent validation errors
os.environ["ACQUISITION_DIR"] = "/"
os.environ["ARCHIVE_DIR"] = "/"
os.environ["ANALYSIS_DIR"] = "/"
os.environ["OVERLORD_DIR"] = "/"
