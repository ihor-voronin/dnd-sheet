import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { TooltipProvider } from "@radix-ui/react-tooltip";

import { fetchDemoSheet } from "./api";
import { SheetView } from "./features/sheet/SheetView";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

function DemoSheet() {
  const { data, isPending, error } = useQuery({
    queryKey: ["demo-sheet"],
    queryFn: fetchDemoSheet,
  });

  if (isPending) return <p className="status">Завантаження документа…</p>;
  if (error) {
    return (
      <p className="status status--error">
        Не вдалося отримати документ: {error instanceof Error ? error.message : String(error)}
      </p>
    );
  }
  return <SheetView document={data} />;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <main className="app">
          <p className="badge">
            Демо-документ · правила 2014 · оригінал показується за значком «?»
          </p>
          <DemoSheet />
        </main>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
