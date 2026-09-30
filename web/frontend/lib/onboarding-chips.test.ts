import { describe, expect, it } from "vitest";
import { stadtthemaBild, stadtthemaChip } from "./onboarding-chips";

describe("onboarding-chips", () => {
  it("die Kennung hat die Form, die der Server auf seiner Positivliste führt", () => {
    expect(stadtthemaChip("cycling")).toBe("city_topic:cycling");
  });

  it("das Bild liegt unter public/themen/<key>.webp", () => {
    expect(stadtthemaBild("pools")).toBe("/themen/pools.webp");
  });
});
