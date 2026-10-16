# Third-Party Notices

This repository contains and adapts components from:

## Awesome Finance Skills

- Project: [RKiding/Awesome-finance-skills](https://github.com/RKiding/Awesome-finance-skills)
- Copyright: 2026 RKiding
- License: Apache License 2.0
- License file: [LICENSE](LICENSE)

The bundled source modules and
`alphaear-finance/scripts/predictor/predictor/exports/models/kronos_news_v1_20260101_0015.pt`
were distributed by the upstream project under its repository-level Apache
License 2.0.

This Codex packaging changes the skill metadata, documentation, dependency
management, canonical imports, and runtime validation. Those modifications do
not remove or replace the upstream copyright and license terms.

## Kronos

- Project: [shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos)
- Runtime models:
  [NeoQuasar/Kronos-base](https://huggingface.co/NeoQuasar/Kronos-base) and
  [NeoQuasar/Kronos-Tokenizer-base](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-base)
- License identified by the project and model cards: MIT License

The Kronos base model and tokenizer weights are not stored in this repository.
When predictor functionality is used, the runtime may download them from
Hugging Face. Users remain responsible for complying with the applicable model
license and service terms.

## Python dependencies

Python dependencies are resolved from their package indexes and installed into
the local virtual environment; they are not vendored in this repository. Each
dependency remains subject to its own license.
