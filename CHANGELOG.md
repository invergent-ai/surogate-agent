# Changelog

## [1.0.0](https://github.com/invergent-ai/surogate-agent/compare/v0.1.2...v1.0.0) (2026-02-25)


### ⚠ BREAKING CHANGES

* Angular UI

### Features

* [CORE][skill-developer] Always create frontmatter in generated skills ([5f8fbaa](https://github.com/invergent-ai/surogate-agent/commit/5f8fbaa6ecc38c5a9f5344d0e8aa27889862d57a))
* [Core][skill-developer] Rethink helper assets distribution ([656c4c5](https://github.com/invergent-ai/surogate-agent/commit/656c4c5d0435ecc98fe4b4d5fd0890c137fd3495))
* [Frontend] Allow file uploading to the workspace before skill creation ([a94ad5d](https://github.com/invergent-ai/surogate-agent/commit/a94ad5d7818dde165a1f57db343eb6b222817f7f))
* [Frontend] Draggable agent actions section ([0243078](https://github.com/invergent-ai/surogate-agent/commit/0243078cf98494b361b40223e35756a59aa83b8d))
* [Frontend] Drawer panels with multiple snap points ([f31027a](https://github.com/invergent-ai/surogate-agent/commit/f31027a015347202a163c2c4b1b613eab7cb4b4f))
* [Frontend] Responsive layout ([f598f68](https://github.com/invergent-ai/surogate-agent/commit/f598f6804e2bc11c065b78d1f85d0649829a4f16))
* [Frontend] Surogate theme, light & dark modes ([8256d88](https://github.com/invergent-ai/surogate-agent/commit/8256d88d0f9a776d81b624ab48fa469b425ce9dd))
* [Frontend] User defined model and api key ([1cbe54a](https://github.com/invergent-ai/surogate-agent/commit/1cbe54a19772e181a6f3a3983084d9727fe5cdf2))
* Angular UI ([8e71fd1](https://github.com/invergent-ai/surogate-agent/commit/8e71fd1c6e859649eb65145b8be20412ae76338b))
* Separate agent actions panel ([5c24e14](https://github.com/invergent-ai/surogate-agent/commit/5c24e1442b0ba9e8c95d2d3d9fd756fcaa8c11cf))
* text files viewer and editor ([54bcc4e](https://github.com/invergent-ai/surogate-agent/commit/54bcc4eac9558f9a63b26c2a7854764d52c55967))
* Verbose logging ([f94823b](https://github.com/invergent-ai/surogate-agent/commit/f94823bb8ffef797ccd6bd8a85270ef16641cc28))


### Bug Fixes

* [CORE] Fixed source session files for user agents ([bb26227](https://github.com/invergent-ai/surogate-agent/commit/bb26227bdf37b96a35a8743fe51e67356fd7b36f))
* [CORE] More robust skill loader ([f669aa3](https://github.com/invergent-ai/surogate-agent/commit/f669aa37e6ff4c2556a4c03ba8e2d38f69283a83))
* [Core][skill-developer] Fixed allowed-tools format ([fdaf10a](https://github.com/invergent-ai/surogate-agent/commit/fdaf10a409460152438332ac4b117ef181a5985f))
* [CORE][skill-developer] Front matter generation fixes ([4f5ae4f](https://github.com/invergent-ai/surogate-agent/commit/4f5ae4f2ce312ba594d3a849643453b7796dccdb))
* [CORE][skill-developer] never reference assets outside generated skill's folder, silently copy helper files to the target skill ([3348ba5](https://github.com/invergent-ai/surogate-agent/commit/3348ba5cdaf8530e75fa914cefeae50d4aa45c70))
* [Frontend] Tall chat component ([b27fc28](https://github.com/invergent-ai/surogate-agent/commit/b27fc2891d92e12d9ab38f0d6ffe84e5629d2d3f))
* allow execute tool when using FE ([8e8daaf](https://github.com/invergent-ai/surogate-agent/commit/8e8daafd78472550f08453518e3a01c02e3eacd9))
* bugfix user chat stream ([3814f39](https://github.com/invergent-ai/surogate-agent/commit/3814f39459f06241f2fd1aa8dc6c9b1255416f4f))
* fixed file upload ([f0d46c0](https://github.com/invergent-ai/surogate-agent/commit/f0d46c0e142145dea384916e93efb91f68a5325c))
* streamed messages were not visible ([3bbbcdc](https://github.com/invergent-ai/surogate-agent/commit/3bbbcdc71f5328e49c5c8234d73878e1e799aad2))

## [0.1.2](https://github.com/invergent-ai/surogate-agent/compare/v0.1.1...v0.1.2) (2026-02-23)


### Bug Fixes

* anchor runtime data dir patterns in .dockerignore to root ([33c86e0](https://github.com/invergent-ai/surogate-agent/commit/33c86e0bc9c3a9d01e16c9b175c926c456644dbd))
* restore missing builtin skill ([e45ad1c](https://github.com/invergent-ai/surogate-agent/commit/e45ad1cef939a4a231bb295f561d8fd5eec126e9))

## [0.1.1](https://github.com/invergent-ai/surogate-agent/compare/v0.1.0...v0.1.1) (2026-02-23)


### Bug Fixes

* respect SUROGATE_*_DIR env vars in CLI and AgentConfig defaults ([1acd552](https://github.com/invergent-ai/surogate-agent/commit/1acd552d1c03b18daa4688bd4c32d4eb747daaeb))

## 0.1.0 (2026-02-23)


### Features

* initial surogate-agent implementation ([d70dc52](https://github.com/invergent-ai/surogate-agent/commit/d70dc521d577b1fca11b6d9fe145327cb55b3c6b))


### Bug Fixes

* added openai in docker image ([f907a8f](https://github.com/invergent-ai/surogate-agent/commit/f907a8fcbec41b4fc92c44d244d0410d4e752c09))
* fixed release-please trigger ([88d5d8f](https://github.com/invergent-ai/surogate-agent/commit/88d5d8f8117af2878e55be7e9d656222119d7eee))
