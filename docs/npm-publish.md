# npm 发布清单

发小红书 / 对外推广前，建议完成 npm 发布，让用户可直接 `npx source2launch promote . --platform xhs`。

## 发布前

```sh
npm test
npm run check          # test + pack 校验
npm pack --dry-run     # 确认 files 字段
```

## 登录与发布

```sh
npm login
npm publish --access public
```

## 发布后验证

```sh
npx source2launch@latest --version
npx source2launch@latest --help
npx source2launch@latest promote . --platform xhs
```

## README 更新

发布成功后，可将安装区首行改为：

```sh
npx source2launch promote . --platform xhs
```

并保留 GitHub 方式作为备选：

```sh
npm exec --package github:DeLunnLi/Source2Launch -- source2launch promote . --platform xhs
```

## 版本号

- 改 `package.json` 的 `version`
- 更新 `CHANGELOG.md`
- 打 Git tag：`git tag v0.2.0 && git push origin v0.2.0`
