import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import Home from "./pages/Home";
import DashboardLayout from "./components/DashboardLayout";
import Upload from "./pages/Upload";
import Parameters from "./pages/Parameters";
import Profile from "./pages/Profile";
import Settings from "./pages/Settings";
import FlightTestDetail from "./pages/FlightTestDetail";

function Router() {
  return (
    <Switch>
      <Route path="/" component={() => <DashboardLayout><Home /></DashboardLayout>} />
      <Route path="/upload" component={() => <DashboardLayout><Upload /></DashboardLayout>} />
      <Route path="/parameters" component={() => <DashboardLayout><Parameters /></DashboardLayout>} />
      <Route path="/profile" component={() => <DashboardLayout><Profile /></DashboardLayout>} />
      <Route path="/settings" component={() => <DashboardLayout><Settings /></DashboardLayout>} />
      <Route path="/flight-test/:id" component={() => <DashboardLayout><FlightTestDetail /></DashboardLayout>} />
      <Route path="/404" component={NotFound} />
      <Route component={NotFound} />
    </Switch>
  );
}

// NOTE: About Theme
// - First choose a default theme according to your design style (dark or light bg), than change color palette in index.css
//   to keep consistent foreground/background color across components
// - If you want to make theme switchable, pass `switchable` ThemeProvider and use `useTheme` hook

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider
        defaultTheme="light"
        // switchable
      >
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
