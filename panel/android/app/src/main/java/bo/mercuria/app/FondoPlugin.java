package bo.mercuria.app;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import androidx.core.content.ContextCompat;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

/**
 * Ubicación en segundo plano ("Permitir todo el tiempo"), necesaria para avisar de una zona con
 * riesgo con la app cerrada. Android 11+ no la muestra como diálogo: lleva a los ajustes de la app.
 * Se pide aparte y después de la ubicación normal, como exige Android.
 */
@CapacitorPlugin(
    name = "Fondo",
    permissions = { @Permission(alias = "fondo", strings = { Manifest.permission.ACCESS_BACKGROUND_LOCATION }) }
)
public class FondoPlugin extends Plugin {

    private boolean concedido() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            // Android 9 o menos: la ubicación normal ya vale en segundo plano
            return ContextCompat.checkSelfPermission(getContext(), Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || ContextCompat.checkSelfPermission(getContext(), Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        }
        return getPermissionState("fondo") == PermissionState.GRANTED;
    }

    private void responder(PluginCall call) {
        JSObject r = new JSObject();
        r.put("fondo", concedido());
        call.resolve(r);
    }

    @PluginMethod
    public void estado(PluginCall call) { responder(call); }

    @PluginMethod
    public void pedir(PluginCall call) {
        if (concedido() || Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) { responder(call); return; }
        requestPermissionForAlias("fondo", call, "alResponder");
    }

    @PermissionCallback
    private void alResponder(PluginCall call) { responder(call); }

    @PluginMethod
    public void abrirAjustes(PluginCall call) {
        Intent i = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", getContext().getPackageName(), null));
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        getContext().startActivity(i);
        call.resolve();
    }
}
