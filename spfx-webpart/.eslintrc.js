// The @microsoft/eslint-config-spfx package root is NOT a valid ESLint config
// (it exports { Default, React } profiles), and the package has no `exports`
// map, so extends must use the full subpath including `lib/`.
// This web part uses React components, so use the react profile.
module.exports = {
  extends: ['@microsoft/eslint-config-spfx/lib/profiles/react'],
  parserOptions: { tsconfigRootDir: __dirname }
};
