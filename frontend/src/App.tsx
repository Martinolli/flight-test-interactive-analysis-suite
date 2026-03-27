import { Route, Switch } from 'wouter';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import FlightTestDetail from './pages/FlightTestDetail';
import Upload from './pages/Upload';
import Parameters from './pages/Parameters';
import Profile from './pages/Profile';
import Settings from './pages/Settings';
import DocumentLibrary from './pages/DocumentLibrary';
import AIQuery from './pages/AIQuery';

function App() {
  return (
    <AuthProvider>
      <Switch>
        {/* Public */}
        <Route path="/login" component={Login} />

        {/* Protected */}
        <Route path="/">
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        </Route>

        <Route path="/flight-tests/:id">
          <ProtectedRoute>
            <FlightTestDetail />
          </ProtectedRoute>
        </Route>

        <Route path="/upload">
          <ProtectedRoute>
            <Upload />
          </ProtectedRoute>
        </Route>

        <Route path="/parameters">
          <ProtectedRoute>
            <Parameters />
          </ProtectedRoute>
        </Route>

        <Route path="/profile">
          <ProtectedRoute>
            <Profile />
          </ProtectedRoute>
        </Route>

        <Route path="/settings">
          <ProtectedRoute>
            <Settings />
          </ProtectedRoute>
        </Route>

        <Route path="/documents">
          <ProtectedRoute>
            <DocumentLibrary />
          </ProtectedRoute>
        </Route>

        <Route path="/ai-query">
          <ProtectedRoute>
            <AIQuery />
          </ProtectedRoute>
        </Route>

        {/* 404 */}
        <Route>
          <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="text-center">
              <h1 className="text-6xl font-bold text-gray-200 mb-4">404</h1>
              <p className="text-gray-600 mb-6">Page not found</p>
              <a href="/" className="text-blue-600 hover:underline text-sm">
                Return to Dashboard
              </a>
            </div>
          </div>
        </Route>
      </Switch>
    </AuthProvider>
  );
}

export default App;
