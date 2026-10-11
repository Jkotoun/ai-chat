// Run with `pnpm generate:api`; the backend must be running unless OPENAPI_URL points to a file
// (`uv run python -m app.export_openapi > openapi.json` in backend/).
export default {
  input: process.env.OPENAPI_URL ?? "http://localhost:8000/openapi.json",
  output: "src/client",
};
