# Installing as a Claude Code plugin

```
/plugin marketplace add rezar-84/nuhut.ai
/plugin install ai-sdlc@ai-sdlc
```

That gives you the five `/sdlc-*` commands everywhere: `/sdlc-plan`, `/sdlc-review`,
`/sdlc-verify`, `/sdlc-log`, `/sdlc-doctor`.

## The plugin deliberately ships no skills

Skills are model-invoked, so every installed skill's description sits in the context
window of every future turn whether it fires or not. A plugin is global, and the kit's
whole point is that a marketing site should not carry `sdlc-eval-gate` and a data pipeline
should not carry `sdlc-design-review`.

So the plugin carries the commands — which are typed, and therefore free until used — and
the per-project skills are chosen from the project's own facts:

```sh
./install.sh /path/to/project ACME
```

That is where the documentation, the charter, and the selected skills land. The two are
complementary: the plugin makes the loop available, the installer makes it true of a
specific repository.
