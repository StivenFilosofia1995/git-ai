declare module '@changey/react-leaflet-markercluster' {
  import { ComponentType, ReactNode } from 'react'
  interface MarkerClusterGroupProps {
    children?: ReactNode
    chunkedLoading?: boolean
    [key: string]: unknown
  }
  const MarkerClusterGroup: ComponentType<MarkerClusterGroupProps>
  export default MarkerClusterGroup
}
