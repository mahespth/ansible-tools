import java.util.ArrayList;
import java.util.List;

public class HeapOOMTester {
    public static void main(String[] args) {
        System.out.println("=================================================");
        System.out.println("Starting Heap Exhaustion Test...");
        System.out.println("Runtime Max Memory (Heap): " + (Runtime.getRuntime().maxMemory() / 1024 / 1024) + " MB");
        System.out.println("=================================================");

        List<byte[]> memoryHog = new ArrayList<>();
        int count = 0;

        try {
            while (true) {
                // Allocate 10MB chunks quickly to trigger the OOM
                memoryHog.add(new byte[10 * 1024 * 1024]);
                count++;
                System.out.println("Allocated: " + (count * 10) + " MB");
                Thread.sleep(50); // Small pause to watch it climb
            }
        } catch (InterruptedException e) {
            System.err.println("Test interrupted.");
        }
    }
}
