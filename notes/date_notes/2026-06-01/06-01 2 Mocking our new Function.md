

## On Mocking `httpx.get`

Looking back at our Dependency Injection we used for `get_db` FastAPI swapped in a fake version of something at test time. Mocking is a different mechanism for a similar goal. Instead of injecting a fake dependency, we temporarily replace a function or object with a fake one for the duration of a test. 

`unittest.mock.patch` does this for us. We tell it "whenever `checker.py` looks up `httpx.get`" we hand it a fake function instead. Once the test is down the fake gets removed. The fake can return whatever we want. say a fake response object with `.status_code=200` or it can raise `httpx.RequestError` 

## Latency Assertion

we calculate a latency for our `httpx.get` call but for our tests when we mock `httpx.get` it returns instantly (no actual network delay). But `perf_counter()` still measures the tiny amount of time that passed. So asserting that `latency_ms ==30` doesn't really make sense. Instead we can just assert the type of the result and perhaps a suitable range. 
