# Changelog

## [3.0.0](https://github.com/invergent-ai/surogate-agent/compare/v2.0.0...v3.0.0) (2026-03-12)


### ⚠ BREAKING CHANGES

* Support for sub-agent experts

### Features

* Support for models deployed on vLLM, enable/disable thinking mode ([02a03b3](https://github.com/invergent-ai/surogate-agent/commit/02a03b38b2df71f1fec076a9198b0da48e23bd99))
* Support for sub-agent experts ([9a7b1d2](https://github.com/invergent-ai/surogate-agent/commit/9a7b1d2e6ace62146c1bc5f5b5175d34ad0a1dd9))


### Bug Fixes

* added instructions for package installation ([92f8591](https://github.com/invergent-ai/surogate-agent/commit/92f85912b0300551bb3943bf403ed4f9164de62d))
* cap workspace panel height to 50% ([0cf89bb](https://github.com/invergent-ai/surogate-agent/commit/0cf89bb6585f942fc9c6d61729b1c20e5995cc8c))
* clear history determined session file reference loss ([1cad5d0](https://github.com/invergent-ai/surogate-agent/commit/1cad5d01f4dc9ef21e16cf15f137a321c1aeaa1c))
* Fixed user agent access to experts ([e455536](https://github.com/invergent-ai/surogate-agent/commit/e4555368123e292db5b0e38d293877749ecdf9a6))
* full width mode for right developer panel ([eb26f4b](https://github.com/invergent-ai/surogate-agent/commit/eb26f4b127519d2ebdeb075ca8fc888d7f7fb253))
* make workspace panel scrollable ([244f391](https://github.com/invergent-ai/surogate-agent/commit/244f3910df9767e0bcd9d3745afd302a8894ee88))
* openai thinking mode ([5dbd469](https://github.com/invergent-ai/surogate-agent/commit/5dbd469980136b69390ef5a778a0b24cd0c34fd4))
* subagent access to backends and tools ([4faa0e0](https://github.com/invergent-ai/surogate-agent/commit/4faa0e0dc38f98463e589f36d9cb63522ccebec1))
* track general-purpose subagent activity ([d513a50](https://github.com/invergent-ai/surogate-agent/commit/d513a503643d3a2af06e93cc78bcd541320d1364))

## [2.0.0](https://github.com/invergent-ai/surogate-agent/compare/v1.3.1...v2.0.0) (2026-03-08)


### ⚠ BREAKING CHANGES

* MCP support

### Features

* export/import mcp servers ([badc12e](https://github.com/invergent-ai/surogate-agent/commit/badc12e826534ca181e37bf342a449d143ecc51b))
* Export/Import skills ([2292d2a](https://github.com/invergent-ai/surogate-agent/commit/2292d2ac2239c19a8a72b275543a5de2fd504a80))
* HTTP transport mcp servers ([7f1c6ce](https://github.com/invergent-ai/surogate-agent/commit/7f1c6ce6f50fecebdd1eae34702de8ff63bf37b9))
* markdown support for chat component ([2860f6c](https://github.com/invergent-ai/surogate-agent/commit/2860f6ce2f72730d61d7b4cffbf514e682c5a23f))
* MCP support ([2af7a5c](https://github.com/invergent-ai/surogate-agent/commit/2af7a5c6cab097adafa06e85725ef6cb46b6c08a))
* persistent stdio sessions ([1e14b5f](https://github.com/invergent-ai/surogate-agent/commit/1e14b5fe47a5f61941d61f73bd04d9bec96909e2))
* Skill activity panel ([7839719](https://github.com/invergent-ai/surogate-agent/commit/78397196e9d513ba9a2c103734629800ee39d387))


### Bug Fixes

* added mcp workdirs to dockerfile ([af8e59b](https://github.com/invergent-ai/surogate-agent/commit/af8e59b31ccf16fb1f264ab86b18e8e354e66b6f))
* Auto refresh workspace files on agent response ([e7efa78](https://github.com/invergent-ai/surogate-agent/commit/e7efa7838f1d88e64a9959fb6b1766abf9342eae))
* avoid bad frontmatter role and allowed-tools edits ([64f3874](https://github.com/invergent-ai/surogate-agent/commit/64f38740a6369acb4458a8a64c2aeed51172ec7c))
* ensure users can't alter skill.md files ([72a507c](https://github.com/invergent-ai/surogate-agent/commit/72a507c5d0bb525f783445122c3f0bbf189c15dd))
* Fixed .doc,.docx preview (convert to pdf first), added extra production deps to core deps and documented uv sync ([8626cef](https://github.com/invergent-ai/surogate-agent/commit/8626cef78cbecf34e9c064794b6d81912bc38001))
* Reload skill activities ([1a0618b](https://github.com/invergent-ai/surogate-agent/commit/1a0618b5352dff0f2ba494fb78bd0884e610cf5c))
* root dev conversations were loosing context ([467c40f](https://github.com/invergent-ai/surogate-agent/commit/467c40f094643d80129e8bcf6739a305ee4fe78d))
* self-healing mcp servers ([f5bdff7](https://github.com/invergent-ai/surogate-agent/commit/f5bdff7a4069c622b3b5523a4e5afeaef62ed7c6))
* Separate operational db from checkpoints ([a23a797](https://github.com/invergent-ai/surogate-agent/commit/a23a797922ee5d376958639f4f6e675c61467fef))
* Show all skill activations ([ab12d2a](https://github.com/invergent-ai/surogate-agent/commit/ab12d2a84b6393fe9b81bebd5743589824f7dccf))
* test as user sessions lifecycle ([7ad9428](https://github.com/invergent-ai/surogate-agent/commit/7ad9428c82f93b5446e82a945b94e314b7446510))
* Working _root scratch folder ([2705d4e](https://github.com/invergent-ai/surogate-agent/commit/2705d4edf2b2f0a8733f98fcf7c3b5a288968b22))

## [1.3.1](https://github.com/invergent-ai/surogate-agent/compare/v1.3.0...v1.3.1) (2026-03-04)


### Bug Fixes

* Natural skill selection for user agents ([608b106](https://github.com/invergent-ai/surogate-agent/commit/608b106d692747871c9975d145031e3f365ab1cf))

## [1.3.0](https://github.com/invergent-ai/surogate-agent/compare/v1.2.1...v1.3.0) (2026-03-03)


### Features

* Clear conversation context per skill dev session button ([0defc13](https://github.com/invergent-ai/surogate-agent/commit/0defc131cdb4357643a490f516c172813c806f95))
* clear session chat history for user role ([61c2240](https://github.com/invergent-ai/surogate-agent/commit/61c22406e9a9aa583a45b7f9eb1362777e5ae1bd))
* message history navigation per user session and dev skill session ([d9dc2f7](https://github.com/invergent-ai/surogate-agent/commit/d9dc2f75227b948790f58ea96e03570c6d946233))


### Bug Fixes

* Guard angular routes per role ([2bc1bc1](https://github.com/invergent-ai/surogate-agent/commit/2bc1bc15f77892030cf186c3ecdbfec5aea20c27))
* removed technical error messages ([447e23c](https://github.com/invergent-ai/surogate-agent/commit/447e23ce541dc170c46cc2e78ada1ab185dc20b8))

## [1.2.1](https://github.com/invergent-ai/surogate-agent/compare/v1.2.0...v1.2.1) (2026-03-03)


### Bug Fixes

* Relative paths to data folders ([558ac44](https://github.com/invergent-ai/surogate-agent/commit/558ac44fe43952cdcb384f4d0f3338f5af811bb3))

## [1.2.0](https://github.com/invergent-ai/surogate-agent/compare/v1.1.0...v1.2.0) (2026-03-02)


### Features

* [Core] OpenRouter support ([13036ed](https://github.com/invergent-ai/surogate-agent/commit/13036ed83303113d21e2f6f25677cab2df66fbc0))
* Added context of the active skill for developer role ([90c7572](https://github.com/invergent-ai/surogate-agent/commit/90c75728803e01ed7c7533799c84a4b73f5ca5a3))
* Hard backend guards for fileSystem and shell ([c995320](https://github.com/invergent-ai/surogate-agent/commit/c9953204c1ec3dd89cad36e00155faf475a585cb))
* Prompt-level skill access enforcement for DEVELOPER and USER roles ([03cc93c](https://github.com/invergent-ai/surogate-agent/commit/03cc93c495d6da285cdcc63a1695ae1c03592e47))
* Python editor ([76886f6](https://github.com/invergent-ai/surogate-agent/commit/76886f6c012849ff72fbb05be18c2226c4d3a230))


### Bug Fixes

* Fixed auto-skill detection in dev chat ([946fac8](https://github.com/invergent-ai/surogate-agent/commit/946fac8f98df90ecfdaf65cc52316232efbb4a9f))
* Navigate through message history ([9b945e7](https://github.com/invergent-ai/surogate-agent/commit/9b945e7c5eee4869930a2727135ae3dfa465bc51))

## [1.1.0](https://github.com/invergent-ai/surogate-agent/compare/v1.0.0...v1.1.0) (2026-02-26)


### Features

* [Frontend] Delete confirmations ([0a6ca2a](https://github.com/invergent-ai/surogate-agent/commit/0a6ca2a8ed6d2100970bbc25c50fa9020de69db0))
* [Frontend] File viewer & full-screen mode ([9c72141](https://github.com/invergent-ai/surogate-agent/commit/9c72141ceec87798d0c3ca84bc8f07fc10e6abbd))
* [Frontend] Multiple file uploads ([7003a64](https://github.com/invergent-ai/surogate-agent/commit/7003a648ae969f1777df6b979894096a2981fa26))
* [Frontend] PDF,Doc,Docx and image viewers ([33eb9ed](https://github.com/invergent-ai/surogate-agent/commit/33eb9edf6a1cdb22878f7587e23aa1b7cf1e7e3a))
* [Frontend] Stop agent button ([ad894d7](https://github.com/invergent-ai/surogate-agent/commit/ad894d7ba06dfb4ca68d2d2bae42c960fca2bb1d))
* UI tweaks ([9c25dc0](https://github.com/invergent-ai/surogate-agent/commit/9c25dc08213079e7ff88369912c1989aef6dbc5b))
* User session management ([fa5177c](https://github.com/invergent-ai/surogate-agent/commit/fa5177cf2e659772b7cedf4e70bb159473c06b47))


### Bug Fixes

* [Frontend] Fixed bad workspace folder behaviour ([7261661](https://github.com/invergent-ai/surogate-agent/commit/726166163c1f8cb322571adfac90d901ef5f4443))
* [Frontend] fixed test sessions ([a8b7bc6](https://github.com/invergent-ai/surogate-agent/commit/a8b7bc66d641b626f3780ee30922674db7470b7c))
* [Frontend] pointer cursors on clickable items and disable label text selection ([1adbade](https://github.com/invergent-ai/surogate-agent/commit/1adbade96aa8a12eb3b7a2af7572b045f6c270ba))
* [Frontend] Skill tabs deletion and left panel interaction ([4ca28f7](https://github.com/invergent-ai/surogate-agent/commit/4ca28f79386982c8002f1195a4e09613eca07c4b))
* [Frontend] synced tab to skill-browser to workspace interaction ([e61e53d](https://github.com/invergent-ai/surogate-agent/commit/e61e53d0d8b25148e6842777ba7c647e1dd36bcb))

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
