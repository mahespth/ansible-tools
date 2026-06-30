import java.net.ServerSocket;
import java.net.InetSocketAddress;

public class BacklogTestServer {
    public static void main(String[] args) throws Exception {
        ServerSocket server = new ServerSocket();
        // Bind to port 8080 with a strict backlog limit of 50
        server.bind(new InetSocketAddress("0.0.0.0", 8080), 50);
        System.out.println("Java server is listening but frozen. Backlog queue is 50.");
        
        // PAUSE THE APP: Intentionally do NOT call server.accept()
        Thread.sleep(Long.MAX_VALUE); 
    }
}
