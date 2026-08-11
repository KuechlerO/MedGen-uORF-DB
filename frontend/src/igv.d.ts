declare module "igv" {
  export type Browser = {
    search: (locus: string) => Promise<void> | void;
  };

  export type CreateBrowserConfig = {
    genome?: string;
    reference?: Record<string, unknown>;
    locus?: string;
    showNavigation?: boolean;
    showRuler?: boolean;
    tracks?: Record<string, unknown>[];
  };

  export function createBrowser(
    element: HTMLElement,
    config: CreateBrowserConfig,
  ): Promise<Browser>;

  export function removeBrowser(browser: Browser): Promise<void> | void;

  const igv: {
    createBrowser: typeof createBrowser;
    removeBrowser: typeof removeBrowser;
  };
  export default igv;
}
