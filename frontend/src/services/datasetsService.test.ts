import { describe, it, expect, vi, beforeEach } from "vitest";
import { searchSingleCell, searchProteomics } from "./datasetsService";

function mockFetch(payload: unknown, ok = true, status = 200) {
  const fn = vi.fn((..._args: Parameters<typeof fetch>) =>
    Promise.resolve({ ok, status, json: () => Promise.resolve(payload) } as Response),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

describe("datasetsService", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("searchSingleCell passes query params and unwraps datasets[]", async () => {
    const fetchFn = mockFetch({ datasets: [{ accession: "GSE1", title: "T" }] });
    const out = await searchSingleCell("immune cells");
    expect(out).toHaveLength(1);
    const calledUrl = String(fetchFn.mock.calls[0][0]);
    expect(calledUrl).toContain("/single-cell/search?");
    expect(calledUrl).toContain("query=immune+cells");
    expect(calledUrl).toContain("organism=Homo+sapiens");
  });

  it("searchProteomics posts a valid query spec (diseaseTerms + therapyScope)", async () => {
    const fetchFn = mockFetch([{ accession: "PXD1", title: "P" }]);
    await searchProteomics("breast cancer");
    const init = fetchFn.mock.calls[0][1] as RequestInit;
    const body = JSON.parse(String(init.body));
    expect(init.method).toBe("POST");
    expect(body.diseaseTerms).toEqual(["breast cancer"]);
    expect(body.therapyScope).toBe("broad");
  });

  it("throws on a non-ok response", async () => {
    mockFetch(null, false, 500);
    await expect(searchSingleCell("x")).rejects.toThrow(/Single-cell search failed/);
  });
});
