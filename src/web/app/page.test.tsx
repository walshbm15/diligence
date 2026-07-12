import { render, screen } from "@testing-library/react";
import Home from "./page";

describe("landing page", () => {
  it("renders the hero heading", () => {
    render(<Home />);
    expect(
      screen.getByRole("heading", { level: 1 }),
    ).toHaveTextContent(/reconciles the numbers/i);
  });

  it("renders primary navigation with section links", () => {
    render(<Home />);
    const nav = screen.getByRole("navigation", { name: /primary/i });
    expect(nav).toBeInTheDocument();
    ["How it works", "The checks", "Principles", "The report", "Roadmap"].forEach(
      (label) => {
        expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
      },
    );
  });

  it("renders early-access mail links", () => {
    render(<Home />);
    const ctas = screen.getAllByRole("link", { name: /request early access/i });
    expect(ctas.length).toBeGreaterThan(0);
    ctas.forEach((cta) =>
      expect(cta).toHaveAttribute("href", expect.stringContaining("mailto:")),
    );
  });

  it("labels the eval metrics as coming from the evaluation suite", () => {
    render(<Home />);
    expect(screen.getByText(/measured on our evaluation suite/i)).toBeInTheDocument();
  });

  it("includes the not-advice disclaimer", () => {
    render(<Home />);
    expect(
      screen.getByText(/not accounting, tax or legal advice/i),
    ).toBeInTheDocument();
  });
});
