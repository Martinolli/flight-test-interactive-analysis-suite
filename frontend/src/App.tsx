import { Route, Switch } from 'wouter';
import { AuthProvider } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import Parameters from './pages/Parameters';
import Profile from './pages/Profile';
import Settings from './pages/Settings';

function App() {
  return (
    <AuthProvider>
      <Switch>
        <Route path="/login" component={Login} />

        <Route path="/">
          <ProtectedRoute>
            <Dashboard />
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

        <Route>
          <div className="min-h-screen flex items-center justify-center bg-gray-50">
            <div className="text-center">
              <h1 className="text-4xl font-bold text-gray-900 mb-4">404</h1>
              <p className="text-gray-600">Page not found</p>
            </div>
          </div>
        </Route>
      </Switch>
    </AuthProvider>
  );
}

export default App;
