from django.urls import path
from analytics import views
urlpatterns=[
 path('',views.guide,name='home'),
 path('guide/',views.guide,name='guide'),
 path('global-pulse/',views.dashboard,{'page':'global'},name='global'),
 path('regional-rhythms/',views.dashboard,{'page':'regional'},name='regional'),
 path('hit-velocity/',views.dashboard,{'page':'velocity'},name='velocity'),
 path('weekly-albums/',views.dashboard,{'page':'weekly'},name='weekly'),
 path('artist-deep-dive/',views.dashboard,{'page':'artist'},name='artist'),
 path('api/global/',views.dashboard_data,{'page':'global'},name='global-data'),
 path('api/regional/',views.dashboard_data,{'page':'regional'},name='regional-data'),
 path('api/velocity/',views.dashboard_data,{'page':'velocity'},name='velocity-data'),
 path('api/weekly/',views.dashboard_data,{'page':'weekly'},name='weekly-data'),
 path('api/artist/',views.dashboard_data,{'page':'artist'},name='artist-data'),
 path('api/table/<str:page>/',views.table_data,name='detail-table-data'),
 path('api/artists/',views.artist_search,name='artist-search'),
 path('api/markets/',views.markets,name='markets'),
 path('api/filter-options/<str:page>/',views.filter_options,name='filter-options'),
 path('api/metadata/weekly/',views.weekly_metadata,name='weekly-metadata'),
 path('api/metadata/',views.metadata,name='metadata'),
 path('health/',views.health,name='health'),
]
