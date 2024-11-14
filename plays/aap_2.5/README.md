Overview of Network Communication Requirements
Here’s a breakdown of the required communication between the components:

Source Component	Destination Component	Port	Protocol	Description
Automation Controller	Automation Hub	443	TCP	Access to collections and content
Automation Controller	EDA	8052	TCP	Event-Driven Ansible API communication
Automation Controller	Platform Gateway	443	TCP	HTTPS access to gateway
Automation Hub	Automation Controller	5432	TCP	Database communication (PostgreSQL)
Automation Hub	Platform Gateway	443	TCP	HTTPS access to gateway
EDA	Automation Controller	8053	TCP	WebSocket communication for event-driven updates
EDA	Redis (internal)	6379	TCP	Redis message queue
Platform Gateway	Automation Controller	8052	TCP	Proxy API communication
