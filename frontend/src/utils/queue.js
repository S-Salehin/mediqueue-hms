import { formatTime } from './format'

export function queueArrivalGuidance(snapshot) {
  if (snapshot?.return_window_start) {
    return `Recommended return window: ${formatTime(snapshot.return_window_start)} to ${formatTime(snapshot.return_window_end)}.`
  }
  return snapshot?.guidance || 'Stay nearby and follow onsite staff guidance.'
}
