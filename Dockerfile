# -- What image are we building from?
FROM python:3.12-slim
# Build our image starting `FROM` an existing image.
# For this one we are using the official Python 3.12 slim image as our base

WORKDIR /app
# Sets the directory we place data into of the image.

# -- Copy files from some build context into the image
COPY requirements.txt .
# `COPY` requirements.txt from the build context (our machine) into
# /app/requirements.txt

# -- Execute a command while build is running
RUN pip install -r requirements.txt
# `RUN` a command during the image building process
# For this we are installing our python dependencies


COPY . .
# `COPY` source code into /app/


# -- Execute a command when the container starts
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
# Set the `CoMmanD` to run once the container starts
# Uvicorn listens on 0.0.0.0 so requests from outside the container
# Can reach the application