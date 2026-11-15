import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MarkdownMessage } from "../components/Chat/MarkdownMessage";

describe("MarkdownMessage", () => {
  afterEach(() => cleanup());

  it("renders headings, inline emphasis, code and lists as semantic elements", () => {
    render(<MarkdownMessage content={"## Phase 1\nBuild **safe** output with `code`.\n\n- First\n- Second"} />);
    expect(screen.getByRole("heading", { level: 2, name: "Phase 1" })).toBeTruthy();
    expect(screen.getByText("safe").tagName).toBe("STRONG");
    expect(screen.getByText("code").tagName).toBe("CODE");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders fenced code without interpreting its contents as markup", () => {
    render(<MarkdownMessage content={"```html\n<script>alert(1)</script>\n```"} />);
    expect(screen.getByText("<script>alert(1)</script>").tagName).toBe("CODE");
    expect(document.querySelector("script")).toBeNull();
  });

  it("only turns HTTP(S) markdown links into clickable links", () => {
    render(<MarkdownMessage content={"[safe](https://example.com) [unsafe](javascript:alert(1))"} />);
    const link = screen.getByRole("link", { name: "safe" });
    expect(link.getAttribute("href")).toBe("https://example.com");
    expect(screen.queryByRole("link", { name: "unsafe" })).toBeNull();
    expect(screen.getByText("[unsafe](javascript:alert(1))")).toBeTruthy();
  });
});
