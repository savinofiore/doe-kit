You can run the test suite with:

    {agent_tests}

Work like this:

1. Write the tests for the new behaviour **first**, and run them — they should fail.
2. Implement until they pass.
3. Review your own diff as a sceptical reviewer would — boundary cases, rounding, behaviour
   the existing suite relied on — and fix what you find. Keep repeating this review pass
   until you have used your budget or have nothing left to fix.
4. Finish with the whole suite green.

**Budget for this task: about {token_budget} tokens.** Keep working — more review passes, more
edge cases, more tests — until you are close to it. Do not stop early to save tokens; the
budget is there to be used.
