# Sample request (fixture)

An example request payload this skill might send, for illustration only.

```
api_key = "not-a-real-credential-000000"
```

This fixture example file deliberately embeds a placeholder string shaped like a hardcoded
credential assignment -- the "secret-in-example-file" defect exercised by Phase 7's
security/sanitization scan. It is not a real credential; the value is an obvious placeholder,
deliberately not shaped like any real credential-issuer's token format, so it won't trip a
push-protection scanner on a real hosting provider.
