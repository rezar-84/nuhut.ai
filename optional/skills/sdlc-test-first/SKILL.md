---
name: sdlc-test-first
description: Write the test before the code it checks, and prove the test can fail. Use when building new behaviour, fixing a defect, or refactoring code that has no tests yet, and whenever about to write tests after the implementation, edit a failing test to make it pass, or call a change covered because a suite is green.
---

# Test first

A test written after the code describes what the code does. A test written before it
describes what the code should do. Only the second one can catch the code being wrong.

The rules this skill applies are in `{{DOCS_DIR}}/process/04-quality-gates.md` and, for a
defect, `{{DOCS_DIR}}/process/05-change-control.md`, "Fixing a defect". The QA playbook is
`{{DOCS_DIR}}/roles/qa.md`.

## The cycle

Take one behaviour at a time, from the plan's acceptance criteria.

1. **Red.** Write one test for the behaviour. Run it with the charter's test command and
   read the failure. It must fail because the behaviour is missing. A test that fails on
   an import error, a typo or a missing fixture has proved nothing yet.
2. **Green.** Write the least code that makes it pass. Run the whole suite, not only the
   new test.
3. **Refactor.** Tidy the code and the test with the suite green. Change no behaviour in
   this step, and commit it apart from the behaviour change.
4. Take the next behaviour.

When the item's tests are in place, prove they bite:

```sh
python3 .ai-sdlc/bin/sdlc.py bite <the charter's test command>
```

It puts the changed product files back to the base, runs the tests, and restores the
files. It passes only when the tests fail without the change and pass with it.

## Which tests to write

- **The cases the plan names**, one test each, named for the behaviour and not for the
  function.
- **The failure paths.** What happens on bad input, a missing record, a timeout, a full
  disk. At Tier 1, also the denied case (the wrong user, the wrong tenant) and the
  malformed case.
- **The boundary.** Empty, one, many, and the value on each side of every limit.
- **For a defect, the reproduction.** It comes first, is committed on its own, and is not
  edited while the fix is written.

Test through the interface a caller uses. A test that reaches into private state breaks
on every refactor and says nothing about behaviour.

## When there are no tests yet

Before changing untested code, pin what it does now: write tests that pass against the
current behaviour, including the behaviour you think is wrong, and commit them. Then
change the code, and change a pinned test only where the plan says the behaviour changes.
Say in the worklog entry which pinned behaviours changed.

## What is not a test

| It looks like a test | Why it is not |
| --- | --- |
| It was written to match what the code returned | It passes for wrong code too |
| It asserts that a mock was called | It tests the mock |
| A snapshot nobody read before accepting | It records the bug with the feature |
| It never failed | Nobody knows whether it can |
| It was edited until it passed | The test now agrees with the defect |
| It is skipped, or its assertion is commented out | It is a comment |

## Do not

- Weaken, skip or delete a failing test to get a green run. If the test is wrong, say so
  and stop; changing it is a human decision.
- Chase a coverage number. The charter sets a threshold or there is none. Covered lines
  with no assertion are worse than uncovered ones, because they look safe.
- Claim a behaviour is tested from memory. Run it and cite the run
  (`python3 .ai-sdlc/bin/sdlc.py verify`).

## When a test cannot be written

Some things cannot be tested from here: a third-party sandbox, a device, a visual
judgment. Do not write a test that pretends. Record the check as *Not run* with the
reason, name who or what can run it, and put the manual steps in the test plan
(`{{DOCS_DIR}}/templates/test-plan.md`).

## Output

For each behaviour: the test's name, the command, the failing output before the change
(one line is enough), and the passing run after. Then the `bite` result. List what was
left untested and why.
