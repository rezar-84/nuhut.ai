# Joining a project that has the kit

Someone already installed Nuhut in the project and committed it. You do not run the
installer. You clone the project, set up the few things git does not carry, and ask
`status` what to do next.

1. **Clone.**

   ```sh
   git clone <the project's URL> && cd <the project>
   ```

2. **Configure the merge driver.** Git does not copy merge driver settings with the
   clone. If the project's `.gitattributes` names one, configure it in your clone:

   ```sh
   python3 .ai-sdlc/bin/sdlc.py fix merge-driver
   ```

   If `.gitattributes` names no merge driver, skip this step. `status` reports a driver
   that is declared but not configured.

3. **Say who you are.** The kit reads `NUHUT_USER`, else `git config user.name`. When the
   project has `docs/project/people.json`, that name must match a handle or a name in it.

   ```sh
   git config user.name            # check it
   export NUHUT_USER=<your handle>  # or set it, for this shell
   ```

   If you are not in `people.json`, ask the owner to add you. `status` reports a name it
   cannot map.

4. **Check GitHub access.** Tier 1 approvals go through GitHub, so the GitHub CLI must be
   installed and logged in once the project has open Tier 1 items.

   ```sh
   gh auth status
   ```

5. **Ask what to do next.**

   ```sh
   python3 .ai-sdlc/bin/sdlc.py status
   ```

   It lists any setup still missing, each with its fix, then:
   - the items you hold and the next step each one owes
   - items waiting on you
   - Ready items you could take, with the `claim` command
   - the doctor finding count

   `status --json` prints the same for scripts.

Then read `AGENTS.md` and `docs/CARD.md` (or your project's docs folder), and take an
item with `python3 .ai-sdlc/bin/sdlc.py claim <ID>`. Working beside other agents:
[multi-agent.md](multi-agent.md). Every command: [cli.md](cli.md).
