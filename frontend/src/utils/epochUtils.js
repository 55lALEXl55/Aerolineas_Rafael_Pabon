import dayjs from 'dayjs'
import utc from 'dayjs/plugin/utc'
import timezone from 'dayjs/plugin/timezone'

dayjs.extend(utc)
dayjs.extend(timezone)

export const epochToLocal = (epoch, tz = 'UTC') => {
  if (!epoch) return '—'
  try {
    return dayjs.unix(epoch).tz(tz).format('DD/MM/YYYY HH:mm')
  } catch {
    return dayjs.unix(epoch).utc().format('DD/MM/YYYY HH:mm') + ' UTC'
  }
}

export const epochToDate = (epoch) => {
  if (!epoch) return '—'
  return dayjs.unix(epoch).utc().format('DD/MM/YYYY')
}

export const epochToTime = (epoch, tz = 'UTC') => {
  if (!epoch) return '—'
  try {
    return dayjs.unix(epoch).tz(tz).format('HH:mm')
  } catch {
    return dayjs.unix(epoch).utc().format('HH:mm')
  }
}

export const dateToEpoch = (dateStr) => {
  if (!dateStr) return null
  return dayjs(dateStr).utc().unix()
}

export const durationStr = (minutes, t) => {
  if (!minutes) return '—'
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${h}${t ? t('common.hours') : 'h'} ${m}${t ? t('common.minutes') : 'min'}`
}

export const nowEpoch = () => Math.floor(Date.now() / 1000)
