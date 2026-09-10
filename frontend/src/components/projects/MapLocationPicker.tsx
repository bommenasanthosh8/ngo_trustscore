import { useState, useEffect, type MouseEvent, type ChangeEvent } from 'react'
import { projectsApi } from '@/api/projects'
import type { LocationSearchResult, ProjectLocationInput } from '@/types'

interface MapLocationPickerProps {
  value: ProjectLocationInput
  onChange: (loc: ProjectLocationInput) => void
}


export default function MapLocationPicker({ value, onChange }: MapLocationPickerProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState<LocationSearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const [gpsLoading, setGpsLoading] = useState(false)
  const [gpsError, setGpsError] = useState<string | null>(null)
  const [gpsSuccessMsg, setGpsSuccessMsg] = useState<string | null>(null)

  // Map viewport bounds (centered on user's location or national geographic center)
  const [mapCenter, setMapCenter] = useState({
    lat: value.latitude && value.latitude !== 0 ? value.latitude : 20.5937,
    lon: value.longitude && value.longitude !== 0 ? value.longitude : 78.9629,
  })

  // Only capture GPS when user clicks the Detect Location button

  // Capture user's real physical geographic location with high accuracy
  async function handleCaptureRealLocation(isInitial = false) {
    if (!navigator.geolocation) {
      setGpsError('Geolocation is not supported by your browser.')
      return
    }
    setGpsLoading(true)
    setGpsError(null)

    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const lat = Number(pos.coords.latitude.toFixed(6))
        const lon = Number(pos.coords.longitude.toFixed(6))
        const acc = Number(pos.coords.accuracy.toFixed(1))

        let resolvedName = `Live Physical Site (${lat}°, ${lon}°)`

        // Fast reverse-geocode with 1.5s AbortController timeout to prevent page freezing
        const controller = new AbortController()
        const timeoutId = setTimeout(() => controller.abort(), 1500)
        try {
          const resp = await fetch(
            `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}&zoom=14`,
            { signal: controller.signal, headers: { Accept: 'application/json' } }
          )
          clearTimeout(timeoutId)
          if (resp.ok) {
            const data = await resp.json()
            if (data.display_name) {
              const parts = data.display_name.split(',').slice(0, 3).join(', ')
              resolvedName = parts || resolvedName
            }
          }
        } catch {
          // Non-blocking fallback
        }

        onChange({
          ...value,
          location_name: (!value.location_name || isInitial || value.location_name.includes('Site (')) ? resolvedName : value.location_name,
          latitude: lat,
          longitude: lon,
          gps_accuracy: acc,
          selection_method: 'GPS_DEVICE',
        })
        setMapCenter({ lat, lon })
        setGpsLoading(false)
        setGpsSuccessMsg(`Accurate GPS Coordinates Detected: ${lat.toFixed(6)}° N, ${lon.toFixed(6)}° E (±${acc}m accuracy)`)
      },
      (err) => {
        setGpsLoading(false)
        if (!isInitial) {
          setGpsError(`Unable to retrieve GPS lock: ${err.message}. Please verify device permissions or select a location below.`)
        }
      },
      { enableHighAccuracy: true, timeout: 6000, maximumAge: 10000 }
    )
  }

  // Handle manual latitude change
  function handleLatitudeChange(e: ChangeEvent<HTMLInputElement>) {
    const val = parseFloat(e.target.value)
    if (!isNaN(val) && val >= -90 && val <= 90) {
      onChange({
        ...value,
        latitude: Number(val.toFixed(6)),
        selection_method: 'MANUAL_COORDINATES',
      })
      setMapCenter((prev) => ({ ...prev, lat: val }))
    }
  }

  // Handle manual longitude change
  function handleLongitudeChange(e: ChangeEvent<HTMLInputElement>) {
    const val = parseFloat(e.target.value)
    if (!isNaN(val) && val >= -180 && val <= 180) {
      onChange({
        ...value,
        longitude: Number(val.toFixed(6)),
        selection_method: 'MANUAL_COORDINATES',
      })
      setMapCenter((prev) => ({ ...prev, lon: val }))
    }
  }

  // Debounced location search
  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.length < 2) {
      setSearchResults([])
      return
    }
    const timer = setTimeout(() => {
      setIsSearching(true)
      projectsApi
        .searchLocations(searchQuery)
        .then((res) => {
          if (res.data.success && res.data.data) {
            setSearchResults(res.data.data)
          }
        })
        .catch(console.error)
        .finally(() => setIsSearching(false))
    }, 250)

    return () => clearTimeout(timer)
  }, [searchQuery])

  // Select location from search suggestions
  function handleSelectSuggestion(loc: LocationSearchResult) {
    onChange({
      ...value,
      location_name: loc.display_name,
      latitude: loc.latitude,
      longitude: loc.longitude,
      selection_method: 'SEARCH_LOCATION',
    })
    setMapCenter({ lat: loc.latitude, lon: loc.longitude })
    setSearchQuery('')
    setSearchResults([])
  }

  // Click on map to select point
  function handleMapClick(e: MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top) / rect.height

    const span = 0.8
    const selectedLat = Number((mapCenter.lat + (0.5 - y) * span).toFixed(6))
    const selectedLon = Number((mapCenter.lon + (x - 0.5) * span).toFixed(6))

    onChange({
      ...value,
      latitude: selectedLat,
      longitude: selectedLon,
      selection_method: 'MAP_CLICK',
    })
  }

  return (
    <div className="space-y-4">
      {/* ── Search & GPS Detection Bar ───────────────────────────────── */}
      <div className="space-y-1.5">
        <label className="form-label">Search Location or Use Device GPS</label>
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              placeholder="Search site, city, or landmark..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="input-field text-sm"
            />
            {isSearching && (
              <div className="absolute right-3 top-2.5 text-xs text-slate-400">Searching…</div>
            )}

            {searchResults.length > 0 && (
              <div className="absolute z-20 left-0 right-0 mt-1 rounded-xl bg-surface-card border border-surface-border shadow-2xl overflow-hidden max-h-56 overflow-y-auto">
                {searchResults.map((item, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSelectSuggestion(item)}
                    className="w-full text-left px-4 py-2.5 hover:bg-brand-900/30 text-xs border-b border-surface-border/50 transition-colors flex items-center justify-between"
                  >
                    <div>
                      <div className="font-medium text-white">{item.location_name}</div>
                      <div className="text-slate-400">{item.display_name}</div>
                    </div>
                    <span className="text-brand-400 font-mono text-[10px]">
                      {item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={() => handleCaptureRealLocation(false)}
            disabled={gpsLoading}
            className="btn-secondary text-xs flex items-center justify-center gap-1.5 whitespace-nowrap px-4 py-2.5"
          >
            {gpsLoading ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
                <span>Detecting GPS…</span>
              </>
            ) : (
              <>
                <span>📡</span>
                <span>Detect Current Location</span>
              </>
            )}
          </button>
        </div>

        {gpsSuccessMsg && (
          <div className="text-[11px] text-emerald-400 font-mono flex items-center gap-1.5 pt-0.5">
            <span>✓</span> {gpsSuccessMsg}
          </div>
        )}
        {gpsError && (
          <div className="text-[11px] text-rose-400 flex items-center gap-1.5 pt-0.5">
            <span>⚠️</span> {gpsError}
          </div>
        )}
      </div>

      {/* ── Coordinate Inputs (Latitude / Longitude) ──────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 rounded-xl bg-surface-card border border-surface-border">
        <div>
          <label className="text-xs font-semibold text-slate-300 mb-1 flex items-center justify-between">
            <span>Latitude *</span>
            <span className="text-[10px] text-slate-500 font-mono">-90 to +90</span>
          </label>
          <div className="relative">
            <input
              type="number"
              step="0.000001"
              min="-90"
              max="90"
              required
              value={value.latitude && value.latitude !== 0 ? value.latitude : ''}
              onChange={handleLatitudeChange}
              placeholder="e.g. 25.317645"
              className="input-field text-sm font-mono"
            />
            <span className="absolute right-3 top-2.5 text-xs text-slate-500 font-mono">° N</span>
          </div>
        </div>

        <div>
          <label className="text-xs font-semibold text-slate-300 mb-1 flex items-center justify-between">
            <span>Longitude *</span>
            <span className="text-[10px] text-slate-500 font-mono">-180 to +180</span>
          </label>
          <div className="relative">
            <input
              type="number"
              step="0.000001"
              min="-180"
              max="180"
              required
              value={value.longitude && value.longitude !== 0 ? value.longitude : ''}
              onChange={handleLongitudeChange}
              placeholder="e.g. 82.973912"
              className="input-field text-sm font-mono"
            />
            <span className="absolute right-3 top-2.5 text-xs text-slate-500 font-mono">° E</span>
          </div>
        </div>
      </div>

      {/* ── Interactive Map Pin Viewport ──────────────────────────────── */}
      <div className="space-y-1.5">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>Click anywhere on the map to pin the project site</span>
          <span className="font-mono text-brand-300">
            {value.latitude ? `${value.latitude.toFixed(6)}° N` : '—'}, {value.longitude ? `${value.longitude.toFixed(6)}° E` : '—'}
          </span>
        </div>

        <div
          onClick={handleMapClick}
          className="relative h-52 w-full rounded-2xl overflow-hidden border border-surface-border bg-slate-950 cursor-crosshair select-none"
          style={{
            backgroundImage: `radial-gradient(circle at 50% 50%, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 1) 100%), 
                              linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px)`,
            backgroundSize: '100% 100%, 28px 28px, 28px 28px',
          }}
        >
          {/* Center Pin & Geofence Boundary */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div
              className="rounded-full border border-brand-500/50 bg-brand-500/10 transition-all duration-200"
              style={{
                width: `${Math.min(200, Math.max(40, (value.geofence_radius || 500) / 10))}px`,
                height: `${Math.min(200, Math.max(40, (value.geofence_radius || 500) / 10))}px`,
              }}
            />
            <div className="absolute flex flex-col items-center">
              <div className="w-4 h-4 rounded-full bg-rose-500 border-2 border-white shadow-md shadow-rose-500/50" />
              <div className="w-1.5 h-1.5 rounded-full bg-rose-600 -mt-0.5" />
            </div>
          </div>
        </div>
      </div>

      {/* ── Site Name & Geofence Radius ──────────────────────────────── */}
      <div className="space-y-3">
        <div>
          <label className="form-label">Project Site Name / Location *</label>
          <input
            type="text"
            required
            placeholder="e.g. Rampur Village Community Center, Ward 4"
            value={value.location_name}
            onChange={(e) => onChange({ ...value, location_name: e.target.value })}
            className="input-field text-sm"
          />
        </div>

        <div className="p-3.5 rounded-xl bg-surface-card border border-surface-border space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-white font-medium">Geofence Radius:</span>
            <span className="text-brand-400 font-semibold font-mono">
              {value.geofence_radius || 500} meters (± {((value.geofence_radius || 500) / 1000).toFixed(2)} km)
            </span>
          </div>
          <input
            type="range"
            min={50}
            max={3000}
            step={50}
            value={value.geofence_radius || 500}
            onChange={(e) => onChange({ ...value, geofence_radius: Number(e.target.value) })}
            className="w-full accent-brand-500 cursor-pointer"
          />
          <p className="text-[11px] text-slate-400">
            Evidence uploaded for milestones must originate within this geofence boundary.
          </p>
        </div>
      </div>
    </div>
  )
}

