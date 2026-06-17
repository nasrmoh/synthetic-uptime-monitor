In our dockerfile when replace the line
`CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]`

With the line
`CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1"]`

We are telling uvicorn to only accept connections from inside the container itself.
Even Though Docker does forward traffic from the host machine to the container uvicorn
will not accept it.
