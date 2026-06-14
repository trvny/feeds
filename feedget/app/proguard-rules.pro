# Keep AppWidgetProvider, RemoteViewsService and the factory — referenced from the
# manifest / framework via reflection, so R8 must not strip or rename them.
-keep class com.fidy.widget.** { *; }
