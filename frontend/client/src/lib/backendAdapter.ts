import axios from 'axios';

// Create API client that talks to your FastAPI backend
const api = axios.create({
        baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add JWT token to all requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Adapter that makes tRPC calls work with your REST API
export const backendAdapter = {
  // Flight Tests API
  flightTests: {
    list: {
      useQuery: () => {
        const [data, setData] = useState<any[]>([]);
        const [isLoading, setIsLoading] = useState(true);
        const [error, setError] = useState<Error | null>(null);

        useEffect(() => {
          api.get('/api/flight-tests/')
            .then(res => {
              setData(res.data);
              setIsLoading(false);
            })
            .catch(err => {
              setError(err);
              setIsLoading(false);
            });
        }, []);

        return { data, isLoading, error };
      },
    },
    create: {
      useMutation: () => {
        return {
          mutateAsync: async (input: any) => {
            const { data } = await api.post('/api/flight-tests/', input);
            return data;
          },
        };
      },
    },
    getById: {
      useQuery: (params: { id: number }) => {
        const [data, setData] = useState<any>(null);
        const [isLoading, setIsLoading] = useState(true);
        const [error, setError] = useState<Error | null>(null);

        useEffect(() => {
          if (params.id) {
            api.get(`/api/flight-tests/${params.id}`)
              .then(res => {
                setData(res.data);
                setIsLoading(false);
              })
              .catch(err => {
                setError(err);
                setIsLoading(false);
              });
          }
        }, [params.id]);

        return { data, isLoading, error };
      },
    },
    update: {
      useMutation: () => {
        return {
          mutateAsync: async ({ id, ...input }: any) => {
            await api.put(`/api/flight-tests/${id}`, input);
            return { success: true };
          },
        };
      },
    },
    delete: {
      useMutation: () => {
        return {
          mutateAsync: async ({ id }: { id: number }) => {
            await api.delete(`/api/flight-tests/${id}`);
            return { success: true };
          },
        };
      },
    },
  },

  // Parameters API
  parameters: {
    list: {
      useQuery: () => {
        const [data, setData] = useState<any[]>([]);
        const [isLoading, setIsLoading] = useState(true);
        const [error, setError] = useState<Error | null>(null);

        useEffect(() => {
          api.get('/api/parameters/')
            .then(res => {
              setData(res.data);
              setIsLoading(false);
            })
            .catch(err => {
              setError(err);
              setIsLoading(false);
            });
        }, []);

        return { data, isLoading, error };
      },
    },
    create: {
      useMutation: () => {
        return {
          mutateAsync: async (input: any) => {
            const { data } = await api.post('/api/parameters/', input);
            return data;
          },
        };
      },
    },
  },

  // Data Points API
  dataPoints: {
    getByFlightTest: {
      useQuery: (params: { flightTestId: number }) => {
        const [data, setData] = useState<any[]>([]);
        const [isLoading, setIsLoading] = useState(true);
        const [error, setError] = useState<Error | null>(null);

        useEffect(() => {
          if (params.flightTestId) {
            api.get(`/api/flight-tests/${params.flightTestId}/data-points`)
              .then(res => {
                setData(res.data);
                setIsLoading(false);
              })
              .catch(err => {
                setError(err);
                setIsLoading(false);
              });
          }
        }, [params.flightTestId]);

        return { data, isLoading, error };
      },
    },
  },

  // Authentication API
  auth: {
    me: {
      useQuery: () => {
        const [data, setData] = useState<any>(null);
        const [isLoading, setIsLoading] = useState(true);
        const [error, setError] = useState<Error | null>(null);

        useEffect(() => {
          const token = localStorage.getItem('access_token');
          if (token) {
            api.get('/api/auth/me')
              .then(res => {
                setData(res.data);
                setIsLoading(false);
              })
              .catch(err => {
                setError(err);
                setIsLoading(false);
              });
          } else {
            setIsLoading(false);
          }
        }, []);

        return { data, isLoading, error };
      },
    },
    logout: {
      useMutation: () => {
        return {
          mutateAsync: async () => {
            localStorage.removeItem('access_token');
            return { success: true };
          },
        };
      },
    },
  },
};

// Import React hooks at the top
import { useState, useEffect } from 'react';
