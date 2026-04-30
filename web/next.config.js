const { execSync } = require("node:child_process");

function gitSha() {
  try {
    return execSync("git rev-parse --short HEAD").toString().trim();
  } catch {
    return "unknown";
  }
}

// When deploying to GitHub Pages under /zerve-odsc-ai-datathon, set
// GITHUB_PAGES=true at build time. Local `npm run dev` and Vercel deploys
// keep the empty basePath so absolute paths work.
const isPages = process.env.GITHUB_PAGES === "true";
const basePath = isPages ? "/zerve-odsc-ai-datathon" : "";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  images: { unoptimized: true },
  reactStrictMode: true,
  basePath,
  assetPrefix: basePath || undefined,
  trailingSlash: true,
  env: {
    NEXT_PUBLIC_BUILD_SHA: gitSha(),
    NEXT_PUBLIC_BUILD_TIME: new Date().toISOString(),
    NEXT_PUBLIC_BASE_PATH: basePath,
  },
};
module.exports = nextConfig;
