package bo.mercuria.app;

import android.os.Bundle;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(FondoPlugin.class);   // plugin propio: ubicación "Permitir todo el tiempo"
        super.onCreate(savedInstanceState);
    }
}
