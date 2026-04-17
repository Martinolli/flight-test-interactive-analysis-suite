import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CheckSquare,
  Search,
  Square,
  Star,
  Trash2,
} from 'lucide-react';
import { ParameterInfo } from '../services/api';
import { cn } from '../lib/utils';

interface SavedParameterSet {
  name: string;
  parameters: string[];
  created_at: string;
}

interface ParameterExplorerPanelProps {
  parameters: ParameterInfo[];
  selectedParams: Set<string>;
  maxSelection?: number;
  storageNamespace: string;
  onToggleParam: (name: string) => void;
  onApplyParameterSet: (names: string[]) => void;
}

function deriveGroupKey(name: string): string {
  if (name.includes('_')) {
    return name.split('_')[0] || 'GENERAL';
  }
  if (name.includes('.')) {
    return name.split('.')[0] || 'GENERAL';
  }
  const alphaPrefix = name.match(/^[A-Za-z]+/)?.[0];
  if (alphaPrefix && alphaPrefix.length >= 3) {
    return alphaPrefix.slice(0, 6).toUpperCase();
  }
  return 'GENERAL';
}

function normalizeSetName(name: string): string {
  return name.trim().replace(/\s+/g, ' ');
}

export default function ParameterExplorerPanel({
  parameters,
  selectedParams,
  maxSelection = 8,
  storageNamespace,
  onToggleParam,
  onApplyParameterSet,
}: ParameterExplorerPanelProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
  const [favorites, setFavorites] = useState<string[]>([]);
  const [savedSets, setSavedSets] = useState<SavedParameterSet[]>([]);
  const [setNameInput, setSetNameInput] = useState('');
  const [selectedSetName, setSelectedSetName] = useState('');
  const loadedFavoritesKeyRef = useRef<string | null>(null);
  const loadedSetsKeyRef = useRef<string | null>(null);
  const [favoritesHydrated, setFavoritesHydrated] = useState(false);
  const [savedSetsHydrated, setSavedSetsHydrated] = useState(false);

  const favoritesStorageKey = `ftias:param-explorer:${storageNamespace}:favorites`;
  const setsStorageKey = `ftias:param-explorer:${storageNamespace}:sets`;

  useEffect(() => {
    // Reset hydration guards whenever key scope changes.
    setFavoritesHydrated(false);
    setSavedSetsHydrated(false);

    try {
      const rawFavorites = localStorage.getItem(favoritesStorageKey);
      const parsedFavorites = rawFavorites ? JSON.parse(rawFavorites) : [];
      const safeFavorites = Array.isArray(parsedFavorites)
        ? parsedFavorites.filter((v): v is string => typeof v === 'string')
        : [];
      setFavorites(safeFavorites);
    } catch {
      setFavorites([]);
    } finally {
      loadedFavoritesKeyRef.current = favoritesStorageKey;
      // Hydration completes in this render cycle; write effects must wait until
      // the next render to avoid clobbering persisted data with initial [] state.
      setFavoritesHydrated(true);
    }

    try {
      const rawSets = localStorage.getItem(setsStorageKey);
      const parsedSets = rawSets ? JSON.parse(rawSets) : [];
      const safeSets = Array.isArray(parsedSets)
        ? parsedSets
            .filter(
              (entry): entry is SavedParameterSet =>
                !!entry &&
                typeof entry.name === 'string' &&
                Array.isArray(entry.parameters)
            )
            .map((entry) => ({
              name: entry.name,
              parameters: entry.parameters.filter((p): p is string => typeof p === 'string'),
              created_at: typeof entry.created_at === 'string' ? entry.created_at : new Date().toISOString(),
            }))
        : [];
      setSavedSets(safeSets);
      setSelectedSetName((prev) => {
        if (prev && safeSets.some((entry) => entry.name === prev)) {
          return prev;
        }
        return safeSets[0]?.name ?? '';
      });
    } catch {
      setSavedSets([]);
      setSelectedSetName('');
    } finally {
      loadedSetsKeyRef.current = setsStorageKey;
      // Same guard rationale as favorites.
      setSavedSetsHydrated(true);
    }
  }, [favoritesStorageKey, setsStorageKey]);

  useEffect(() => {
    if (!favoritesHydrated || loadedFavoritesKeyRef.current !== favoritesStorageKey) {
      return;
    }
    localStorage.setItem(favoritesStorageKey, JSON.stringify(favorites));
  }, [favorites, favoritesStorageKey, favoritesHydrated]);

  useEffect(() => {
    if (!savedSetsHydrated || loadedSetsKeyRef.current !== setsStorageKey) {
      return;
    }
    localStorage.setItem(setsStorageKey, JSON.stringify(savedSets));
  }, [savedSets, setsStorageKey, savedSetsHydrated]);

  const favoriteSet = useMemo(() => new Set(favorites), [favorites]);

  const filteredParameters = useMemo(() => {
    const term = searchTerm.trim().toLowerCase();
    return parameters.filter((param) => {
      if (showFavoritesOnly && !favoriteSet.has(param.name)) {
        return false;
      }
      if (!term) {
        return true;
      }
      const haystack = `${param.name} ${param.unit ?? ''}`.toLowerCase();
      return haystack.includes(term);
    });
  }, [favoriteSet, parameters, searchTerm, showFavoritesOnly]);

  const groupedParameters = useMemo(() => {
    const groupMap = new Map<string, ParameterInfo[]>();
    for (const param of filteredParameters) {
      const key = deriveGroupKey(param.name);
      if (!groupMap.has(key)) {
        groupMap.set(key, []);
      }
      groupMap.get(key)?.push(param);
    }
    return Array.from(groupMap.entries())
      .map(([group, items]) => ({
        group,
        items: [...items].sort((a, b) => a.name.localeCompare(b.name)),
      }))
      .sort((a, b) => a.group.localeCompare(b.group));
  }, [filteredParameters]);

  function toggleFavorite(name: string) {
    setFavorites((prev) => {
      if (prev.includes(name)) {
        return prev.filter((entry) => entry !== name);
      }
      return [...prev, name].sort((a, b) => a.localeCompare(b));
    });
  }

  function saveCurrentSelectionAsSet() {
    const normalizedName = normalizeSetName(setNameInput);
    if (!normalizedName || selectedParams.size === 0) {
      return;
    }

    const nextEntry: SavedParameterSet = {
      name: normalizedName,
      parameters: Array.from(selectedParams).sort((a, b) => a.localeCompare(b)),
      created_at: new Date().toISOString(),
    };

    setSavedSets((prev) => {
      const withoutSameName = prev.filter((entry) => entry.name !== normalizedName);
      return [...withoutSameName, nextEntry].sort((a, b) => a.name.localeCompare(b.name));
    });
    setSelectedSetName(normalizedName);
    setSetNameInput('');
  }

  function applySelectedSet() {
    if (!selectedSetName) {
      return;
    }
    const chosen = savedSets.find((entry) => entry.name === selectedSetName);
    if (!chosen) {
      return;
    }
    onApplyParameterSet(chosen.parameters);
  }

  function deleteSelectedSet() {
    if (!selectedSetName) {
      return;
    }
    setSavedSets((prev) => {
      const next = prev.filter((entry) => entry.name !== selectedSetName);
      setSelectedSetName(next[0]?.name ?? '');
      return next;
    });
  }

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-2.5">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-gray-400" />
          <input
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search parameters…"
            className="w-full rounded-lg border border-gray-200 bg-white py-1.5 pl-8 pr-2 text-sm
                       text-gray-800 placeholder:text-gray-400 focus:outline-none focus:ring-2
                       focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div className="mt-2 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setShowFavoritesOnly((v) => !v)}
            className={cn(
              'inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs transition-colors',
              showFavoritesOnly
                ? 'border-amber-300 bg-amber-50 text-amber-700'
                : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
            )}
          >
            <Star className="h-3.5 w-3.5" />
            Favorites
          </button>
          <span className="text-xs text-gray-500">
            {selectedParams.size}/{maxSelection} selected
          </span>
        </div>
      </div>

      <div className="rounded-lg border border-gray-200 bg-gray-50 p-2.5 space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-600">
          Saved Parameter Sets
        </p>
        <div className="flex gap-2">
          <input
            value={setNameInput}
            onChange={(e) => setSetNameInput(e.target.value)}
            placeholder="Set name"
            className="w-full rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800
                       placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500
                       focus:border-transparent"
          />
          <button
            type="button"
            onClick={saveCurrentSelectionAsSet}
            disabled={!setNameInput.trim() || selectedParams.size === 0}
            className="shrink-0 rounded-md border border-blue-200 px-2 py-1.5 text-xs font-medium
                       text-blue-700 transition-colors hover:bg-blue-50 disabled:cursor-not-allowed
                       disabled:opacity-50"
          >
            Save
          </button>
        </div>
        <div className="flex gap-2">
          <select
            value={selectedSetName}
            onChange={(e) => setSelectedSetName(e.target.value)}
            disabled={savedSets.length === 0}
            className="w-full rounded-md border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-800
                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                       disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="">
              {savedSets.length === 0 ? 'No saved sets yet' : '— Select saved set —'}
            </option>
            {savedSets.map((entry) => (
              <option key={entry.name} value={entry.name}>
                {entry.name} ({entry.parameters.length})
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={applySelectedSet}
            disabled={!selectedSetName}
            className="shrink-0 rounded-md border border-green-200 px-2 py-1.5 text-xs font-medium
                       text-green-700 transition-colors hover:bg-green-50 disabled:cursor-not-allowed
                       disabled:opacity-50"
          >
            Apply
          </button>
          <button
            type="button"
            onClick={deleteSelectedSet}
            disabled={!selectedSetName}
            className="inline-flex shrink-0 items-center rounded-md border border-red-200 px-2 py-1.5
                       text-xs font-medium text-red-700 transition-colors hover:bg-red-50
                       disabled:cursor-not-allowed disabled:opacity-50"
            title="Delete selected set"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {filteredParameters.length === 0 ? (
        <p className="py-4 text-sm text-gray-400">
          No parameters match current filters.
        </p>
      ) : (
        <div className="max-h-[520px] space-y-2 overflow-y-auto pr-1">
          {groupedParameters.map((group) => (
            <div key={group.group} className="rounded-lg border border-gray-100 bg-white">
              <div className="border-b border-gray-100 px-2.5 py-1.5">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">
                  {group.group} ({group.items.length})
                </p>
              </div>
              <ul className="space-y-0.5 p-1.5">
                {group.items.map((param) => {
                  const isSelected = selectedParams.has(param.name);
                  const isFavorite = favoriteSet.has(param.name);
                  return (
                    <li key={param.name}>
                      <button
                        type="button"
                        onClick={() => onToggleParam(param.name)}
                        className={cn(
                          'w-full flex items-start gap-2 px-2 py-1.5 rounded-md text-left text-sm transition-colors',
                          isSelected
                            ? 'bg-blue-50 text-blue-800'
                            : 'text-gray-700 hover:bg-gray-50'
                        )}
                      >
                        {isSelected ? (
                          <CheckSquare className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" />
                        ) : (
                          <Square className="mt-0.5 h-4 w-4 shrink-0 text-gray-400" />
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-medium">{param.name}</p>
                          <p className="truncate text-xs opacity-60">
                            {param.unit ?? 'no unit'} · {param.sample_count.toLocaleString()} pts
                          </p>
                        </div>
                        <span
                          role="button"
                          tabIndex={0}
                          onClick={(event) => {
                            event.preventDefault();
                            event.stopPropagation();
                            toggleFavorite(param.name);
                          }}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                              event.preventDefault();
                              event.stopPropagation();
                              toggleFavorite(param.name);
                            }
                          }}
                          className={cn(
                            'inline-flex rounded p-0.5 transition-colors',
                            isFavorite
                              ? 'text-amber-500 hover:text-amber-600'
                              : 'text-gray-300 hover:text-gray-500'
                          )}
                          aria-label={isFavorite ? 'Remove favorite' : 'Mark as favorite'}
                        >
                          <Star className={cn('h-3.5 w-3.5', isFavorite ? 'fill-current' : '')} />
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
