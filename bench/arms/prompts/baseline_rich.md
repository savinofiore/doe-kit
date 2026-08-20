You can run the test suite with:

    {agent_tests}

Work like this:

1. Write the tests for the new behaviour **first**, and run them — they should fail.
2. Implement until they pass.
3. Review your own diff twice, as a sceptical reviewer would: look for boundary cases,
   rounding, and behaviour the existing suite already relied on. Fix what you find.
4. Finish with the whole suite green.

Take the time this needs. Thoroughness is worth more here than speed.
