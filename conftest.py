# This file must exist at the project root to anchor pytest's import system.
# Without it, pytest cannot resolve `app` as a module when running from the project root.
# It is intentionally empty.
# Honestly, I have no idea why this is the case.
# Keeping it this way lets you run pytest from both the root directory and within /tests directory.