This project uses DOE. Follow it exactly:

1. Run `/directive` — interview, then write the directive (spec + Test Contract) to
   `.doe/directives/NN_*.md` with `STATE: DRAFT`. Write **zero** code in this phase.
2. Stop. A human reviews the directive and sets `STATE: APPROVED`.
3. Run `/execute NN` — baseline, RED, fix, then the green gate.

The protected roots ({protected_roots}) are blocked until an approved directive exists. You
may not edit a pre-existing test unless the directive's test-impact table lists it.

The suite runs with:

    {agent_tests}
