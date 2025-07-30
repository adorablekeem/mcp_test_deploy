FROM python:3.12-slim
ENV DEBIAN_FRONTEND=noninteractive

# Set environment variables in a single layer to reduce image size and improve readability
ENV POETRY_HOME=/opt/poetry \
    PATH="$POETRY_HOME/bin:$PATH" \
    SHELL=/bin/bash \
    VIRTUAL_ENV=/app/.venv \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1

# Install Poetry in a virtual environment for dependency management
RUN python3.12 -m pip install --no-cache-dir poetry==2.1.1 && \
    mkdir -p -m 0600 ~/.ssh && \
    ssh-keyscan bitbucket.org >> ~/.ssh/known_hosts

# Set the working directory to /app. This is where the application code will reside.
WORKDIR /app

# Copy the poetry.lock and pyproject.toml files to the container
COPY pyproject.toml poetry.lock ./

# Install project dependencies via Poetry
RUN --mount=type=ssh poetry install --no-interaction --no-ansi --no-root

# Copy the application code to the container
COPY . .

# Install the application in the container's virtual environment
RUN --mount=type=ssh poetry install --no-interaction --no-ansi --only-root

ENTRYPOINT ["poetry", "run"]
CMD ["python"]
