import { defineConfig } from "vitest/config";

// Pure-helper unit tests run in plain Node — no Workers runtime needed.
// (The exported functions under test are string/parse utilities with no
// bindings or global fetch dependency.)
export default defineConfig({
  test: {
    environment: "node",
    include: ["test/**/*.test.ts"],
  },
});
