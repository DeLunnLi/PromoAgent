# Repo Pulse

Repo Pulse reads GitHub repositories and turns source evidence into concise technical social posts.

![Repo Pulse demo](./docs/demo.gif)

## Quickstart

```sh
npx repo-pulse .
```

## Demo

Try the live demo at https://repo-pulse.vercel.app/demo.

## Usage

```sh
repo-pulse tweet https://github.com/example/repo --json
```

```js
import { summarize } from 'repo-pulse';

await summarize('.');
```
