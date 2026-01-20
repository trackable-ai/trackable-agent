# Trackable Agent Flows Design Document

## Overview

Trackable operates in two distinct modes to provide comprehensive order management:

1. **Offline Flow**: Background processing triggered by incoming emails
2. **Real-time Flow**: Interactive chat sessions initiated by users

This document details the architecture, components, and implementation plan for both flows.

---

## Architecture Diagram

```
                                    ┌─────────────────────────────────────────┐
                                    │              Data Store                 │
                                    │  ┌─────────┐ ┌─────────┐ ┌──────────┐  │
                                    │  │ Orders  │ │ Users   │ │ Policies │  │
                                    │  └────▲────┘ └────▲────┘ └────▲─────┘  │
                                    └───────┼──────────┼───────────┼─────────┘
                                            │          │           │
                    ┌───────────────────────┴──────────┴───────────┴───────────────────┐
                    │                                                                   │
        ┌───────────┴───────────┐                                   ┌──────────────────┴──────────┐
        │     OFFLINE FLOW      │                                   │       REAL-TIME FLOW        │
        │                       │                                   │                             │
        │  ┌─────────────────┐  │                                   │  ┌───────────────────────┐  │
        │  │  Gmail Webhook  │  │                                   │  │    Chat Interface     │  │
        │  │  (Push/Pub-Sub) │  │                                   │  │   (ADK Web/CLI/API)   │  │
        │  └────────┬────────┘  │                                   │  └───────────┬───────────┘  │
        │           │           │                                   │              │              │
        │           ▼           │                                   │              ▼              │
        │  ┌─────────────────┐  │                                   │  ┌───────────────────────┐  │
        │  │ Email Classifier│  │                                   │  │      Root Agent       │  │
        │  │  (order-related │  │                                   │  │  (gemini-2.5-flash)   │  │
        │  │    filter)      │  │                                   │  └───────────┬───────────┘  │
        │  └────────┬────────┘  │                                   │              │              │
        │           │           │                                   │              ▼              │
        │           ▼           │                                   │  ┌───────────────────────┐  │
        │  ┌─────────────────┐  │                                   │  │   Agent Orchestrator  │  │
        │  │ Input Processor │◄─┼───────────────────────────────────┼──►  (routes to subagents)│  │
        │  │    Subagent     │  │                                   │  └───────────┬───────────┘  │
        │  └────────┬────────┘  │                                   │              │              │
        │           │           │                                   │              ▼              │
        │           ▼           │                                   │  ┌───────────────────────┐  │
        │  ┌─────────────────┐  │                                   │  │      Subagents        │  │
        │  │ Order Resolver  │  │                                   │  │  - Input Processor    │  │
        │  │ (create/update) │  │                                   │  │  - Tracking Agent     │  │
        │  └────────┬────────┘  │                                   │  │  - Return Agent       │  │
        │           │           │                                   │  │  - Policy Agent       │  │
        │           ▼           │                                   │  └───────────────────────┘  │
        │  ┌─────────────────┐  │                                   │                             │
        │  │  Intervention   │  │                                   │                             │
        │  │    Engine       │  │                                   │                             │
        │  │ (notifications) │  │                                   │                             │
        │  └─────────────────┘  │                                   │                             │
        │                       │                                   │                             │
        └───────────────────────┘                                   └─────────────────────────────┘
```

---

## Flow 1: Offline (Email-Triggered)

### Purpose

Automatically detect and process order-related emails in the background, creating or updating Order objects without user intervention.

### Trigger Mechanisms

#### Option A: Gmail Push Notifications (Recommended)

```
Gmail API → Cloud Pub/Sub → Cloud Functions/Cloud Run → Trackable Agent
```

- Uses Gmail's `watch()` API to subscribe to inbox changes
- Pub/Sub delivers notifications within seconds of email arrival
- Serverless function triggers processing pipeline

#### Option B: Polling (Fallback)

```
Scheduled Job (cron) → Gmail API Query → Trackable Agent
```

- Periodic polling every N minutes
- Query: `is:unread newer_than:1h (subject:order OR subject:shipped OR subject:delivery)`
- Higher latency, simpler setup

### Component Design

#### 1. Email Watcher Service

```python
class EmailWatcherService:
    """Monitors Gmail for new order-related emails"""

    async def setup_watch(self, user_id: str) -> WatchResponse:
        """Set up Gmail push notifications for a user"""

    async def handle_notification(self, notification: PubSubMessage) -> None:
        """Process incoming Pub/Sub notification"""

    async def get_new_emails(self, user_id: str, history_id: str) -> list[Email]:
        """Fetch new emails since last history_id"""
```

#### 2. Email Classifier

```python
class EmailClassifier:
    """Classifies emails as order-related or not"""

    ORDER_SIGNALS = [
        "order confirmation",
        "your order",
        "order shipped",
        "tracking number",
        "delivery update",
        "out for delivery",
        "delivered",
        "return initiated",
        "refund processed",
    ]

    def classify(self, email: Email) -> EmailClassification:
        """
        Returns:
            - ORDER_CONFIRMATION
            - SHIPPING_UPDATE
            - DELIVERY_NOTIFICATION
            - RETURN_UPDATE
            - REFUND_NOTIFICATION
            - NOT_ORDER_RELATED
        """

    def extract_email_type(self, email: Email) -> OrderEmailType:
        """Determine specific order email type for routing"""
```

#### 3. Order Resolver

```python
class OrderResolver:
    """Resolves extracted data to create or update orders"""

    async def resolve(
        self,
        extracted: ExtractedOrderData,
        user_id: str,
        source_type: SourceType,
        source_id: str,
    ) -> tuple[Order, ResolveAction]:
        """
        Determine if this is a new order or update to existing.

        Returns:
            - (Order, CREATED) - New order created
            - (Order, UPDATED) - Existing order updated
            - (Order, DUPLICATE) - Duplicate email, no action
        """

    async def find_existing_order(
        self,
        merchant_name: str,
        order_number: Optional[str],
        user_id: str,
    ) -> Optional[Order]:
        """Find existing order by merchant + order number"""

    async def merge_order_data(
        self,
        existing: Order,
        new_data: ExtractedOrderData,
    ) -> Order:
        """Merge new information into existing order"""
```

#### 4. Intervention Engine

```python
class InterventionEngine:
    """Determines and schedules proactive interventions"""

    async def evaluate_order(self, order: Order) -> list[Intervention]:
        """
        Evaluate order state and generate interventions:
        - Return window closing soon
        - Delivery confirmed, start return window
        - Shipment delayed
        - Refund expected but not received
        """

    async def schedule_intervention(
        self,
        intervention: Intervention,
        user: User,
    ) -> None:
        """Schedule notification delivery based on user preferences"""
```

### Offline Flow Sequence

```
┌──────────┐     ┌──────────┐     ┌───────────┐     ┌─────────────┐     ┌──────────────┐
│  Gmail   │     │  Pub/Sub │     │  Watcher  │     │ Classifier  │     │   Input      │
│          │     │          │     │  Service  │     │             │     │  Processor   │
└────┬─────┘     └────┬─────┘     └─────┬─────┘     └──────┬──────┘     └──────┬───────┘
     │                │                 │                  │                   │
     │ New Email      │                 │                  │                   │
     ├───────────────►│                 │                  │                   │
     │                │  Notification   │                  │                   │
     │                ├────────────────►│                  │                   │
     │                │                 │                  │                   │
     │                │                 │ Fetch Email      │                   │
     │◄───────────────┼─────────────────┤                  │                   │
     │                │                 │                  │                   │
     │   Email Data   │                 │                  │                   │
     ├───────────────►│─────────────────►                  │                   │
     │                │                 │                  │                   │
     │                │                 │  Classify        │                   │
     │                │                 ├─────────────────►│                   │
     │                │                 │                  │                   │
     │                │                 │  ORDER_RELATED   │                   │
     │                │                 │◄─────────────────┤                   │
     │                │                 │                  │                   │
     │                │                 │        Process Email                 │
     │                │                 ├──────────────────────────────────────►
     │                │                 │                  │                   │
     │                │                 │                  │   ExtractedOrder  │
     │                │                 │◄──────────────────────────────────────┤
     │                │                 │                  │                   │

┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Order      │     │    Data      │     │ Intervention │     │    User      │
│  Resolver    │     │    Store     │     │   Engine     │     │              │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │                    │
       │ Find Existing      │                    │                    │
       ├───────────────────►│                    │                    │
       │                    │                    │                    │
       │   None/Order       │                    │                    │
       │◄───────────────────┤                    │                    │
       │                    │                    │                    │
       │ Create/Update      │                    │                    │
       ├───────────────────►│                    │                    │
       │                    │                    │                    │
       │   Order Saved      │                    │                    │
       │◄───────────────────┤                    │                    │
       │                    │                    │                    │
       │   Evaluate Order   │                    │                    │
       ├────────────────────────────────────────►│                    │
       │                    │                    │                    │
       │                    │                    │ Send Notification  │
       │                    │                    ├───────────────────►│
       │                    │                    │                    │
```

### State Transitions (Offline)

```
Email Type                    Order Status Transition
─────────────────────────────────────────────────────
ORDER_CONFIRMATION     →      DETECTED → CONFIRMED
SHIPPING_UPDATE        →      CONFIRMED → SHIPPED
TRACKING_UPDATE        →      SHIPPED → IN_TRANSIT
DELIVERY_NOTIFICATION  →      IN_TRANSIT → DELIVERED
RETURN_CONFIRMATION    →      DELIVERED → RETURNED
REFUND_NOTIFICATION    →      RETURNED → REFUNDED
```

---

## Flow 2: Real-time (User-Initiated Chat)

### Purpose

Provide interactive assistance when users want to:
- Check order status
- Ask questions about orders
- Initiate returns/exchanges
- Get help with issues
- Manually add orders

### Entry Points

1. **ADK Web UI**: `adk web` - Browser-based chat
2. **ADK CLI**: `adk run trackable` - Terminal chat
3. **API**: Direct API calls for embedded chat widgets

### Component Design

#### 1. Root Agent (Orchestrator)

```python
root_agent = Agent(
    model="gemini-2.5-flash",
    name="root_agent",
    description="Personal shopping assistant for order management",
    instruction="""You are Trackable, a personal shopping assistant.

You help users:
- Track their orders and shipments
- Understand return/exchange policies
- Initiate returns and exchanges
- Resolve order issues
- Add orders from screenshots or manual entry

Always be proactive about:
- Mentioning upcoming return deadlines
- Suggesting actions based on order status
- Asking clarifying questions when needed

Use your subagents for specialized tasks:
- input_processor: Extract orders from images/emails
- tracking_agent: Get real-time shipment updates
- return_agent: Handle return/exchange workflows
- policy_agent: Interpret merchant policies
""",
    sub_agents=[
        input_processor_agent,
        tracking_agent,
        return_agent,
        policy_agent,
    ],
    tools=[
        get_user_orders,
        get_order_details,
        search_orders,
        update_order_status,
    ],
)
```

#### 2. Subagent Routing

```python
class AgentOrchestrator:
    """Routes user intents to appropriate subagents"""

    INTENT_ROUTING = {
        "track_order": "tracking_agent",
        "add_order": "input_processor",
        "return_item": "return_agent",
        "exchange_item": "return_agent",
        "check_policy": "policy_agent",
        "order_status": None,  # Root handles directly
        "list_orders": None,
        "general_help": None,
    }

    async def route(self, user_message: str, context: ChatContext) -> AgentResponse:
        """Determine intent and route to appropriate handler"""
```

#### 3. Context Manager

```python
class ChatContext:
    """Maintains conversation context for coherent interactions"""

    user_id: str
    session_id: str
    current_order: Optional[Order]  # Order being discussed
    conversation_history: list[Message]
    user_preferences: UserPreferences

    async def load_relevant_orders(self) -> list[Order]:
        """Load orders relevant to current conversation"""

    async def get_upcoming_deadlines(self) -> list[Deadline]:
        """Get return/exchange deadlines to proactively mention"""
```

### Real-time Flow Sequence

```
┌──────────┐     ┌──────────┐     ┌───────────┐     ┌─────────────┐     ┌──────────────┐
│   User   │     │   Chat   │     │   Root    │     │  Subagent   │     │    Data      │
│          │     │ Interface│     │   Agent   │     │             │     │    Store     │
└────┬─────┘     └────┬─────┘     └─────┬─────┘     └──────┬──────┘     └──────┬───────┘
     │                │                 │                  │                   │
     │ "Where's my    │                 │                  │                   │
     │  Nike order?"  │                 │                  │                   │
     ├───────────────►│                 │                  │                   │
     │                │ Process Message │                  │                   │
     │                ├────────────────►│                  │                   │
     │                │                 │                  │                   │
     │                │                 │ Load User Orders │                   │
     │                │                 ├──────────────────────────────────────►
     │                │                 │                  │                   │
     │                │                 │    Orders List   │                   │
     │                │                 │◄──────────────────────────────────────┤
     │                │                 │                  │                   │
     │                │                 │ Route: tracking  │                   │
     │                │                 ├─────────────────►│                   │
     │                │                 │                  │                   │
     │                │                 │                  │ Fetch Tracking    │
     │                │                 │                  ├──────────────────►│
     │                │                 │                  │                   │
     │                │                 │  Tracking Status │                   │
     │                │                 │◄─────────────────┤                   │
     │                │                 │                  │                   │
     │                │   Response      │                  │                   │
     │                │◄────────────────┤                  │                   │
     │                │                 │                  │                   │
     │ "Your Nike     │                 │                  │                   │
     │  order is out  │                 │                  │                   │
     │  for delivery" │                 │                  │                   │
     │◄───────────────┤                 │                  │                   │
     │                │                 │                  │                   │
```

### User Intent Examples

| User Says | Intent | Handler | Action |
|-----------|--------|---------|--------|
| "Where's my Amazon order?" | track_order | tracking_agent | Fetch latest tracking |
| "Add this order" + image | add_order | input_processor | Extract from image |
| "I want to return the shoes" | return_item | return_agent | Start return flow |
| "What's Nike's return policy?" | check_policy | policy_agent | Fetch/interpret policy |
| "Show me all my orders" | list_orders | root_agent | Query and display |
| "Is my refund coming?" | track_refund | root_agent | Check refund status |

---

## User Onboarding & OAuth

### Overview

Before the offline flow can monitor a user's inbox, the user must grant Trackable permission to read their Gmail. This is accomplished via OAuth 2.0 with a frontend/backend split architecture.

### Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              ONBOARDING FLOW                                     │
│                                                                                  │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌────────┐ │
│  │ Frontend │     │  Google  │     │ Backend  │     │ Database │     │ Gmail  │ │
│  │ (Web UI) │     │  OAuth   │     │ (Agent)  │     │          │     │  API   │ │
│  └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └───┬────┘ │
│       │                │                │                │               │      │
│       │ 1. Click       │                │                │               │      │
│       │ "Connect Gmail"│                │                │               │      │
│       │                │                │                │               │      │
│       │ 2. Redirect ───────────────────►│                │               │      │
│       │    w/ client_id, scopes         │                │               │      │
│       │                │                │                │               │      │
│       │                │ 3. User grants │                │               │      │
│       │                │    permission  │                │               │      │
│       │                │                │                │               │      │
│       │◄─────────────────────────────────                │               │      │
│       │ 4. Redirect w/ auth code        │                │               │      │
│       │                │                │                │               │      │
│       │ 5. POST /api/oauth/callback ───►│                │               │      │
│       │    { code, user_id }            │                │               │      │
│       │                │                │                │               │      │
│       │                │ 6. Exchange ───────────────────►│               │      │
│       │                │    code for tokens              │               │      │
│       │                │                │                │               │      │
│       │                │◄─────────────────────────────────               │      │
│       │                │ 7. access_token + refresh_token │               │      │
│       │                │                │                │               │      │
│       │                │                │ 8. Store ─────►│               │      │
│       │                │                │    encrypted   │               │      │
│       │                │                │                │               │      │
│       │                │                │ 9. Setup watch() ─────────────►│      │
│       │                │                │                │               │      │
│       │                │                │◄───────────────────────────────│      │
│       │                │                │ 10. historyId, expiration      │      │
│       │                │                │                │               │      │
│       │◄─────────────────────────────────                │               │      │
│       │ 11. Success response            │                │               │      │
│       │                │                │                │               │      │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Required OAuth Scopes

| Scope | Purpose | Sensitivity |
|-------|---------|-------------|
| `gmail.readonly` | Read email content for order extraction | Sensitive |

**Note**: Since `gmail.readonly` is a sensitive scope, the app requires Google verification before production use. Unverified apps display a warning screen to users.

### Data Models

#### Gmail Credentials

```python
class GmailCredentials(BaseModel):
    """Stored OAuth credentials for a user's Gmail access"""

    user_id: str = Field(description="Internal user ID")
    gmail_address: str = Field(description="User's Gmail address")

    # OAuth tokens (stored encrypted)
    access_token: str = Field(description="Short-lived access token")
    refresh_token: str = Field(description="Long-lived refresh token")
    token_expiry: datetime = Field(description="Access token expiration")
    scopes: list[str] = Field(description="Granted OAuth scopes")

    # Gmail watch state
    history_id: str = Field(description="Last processed history ID")
    watch_expiry: datetime = Field(description="When watch() expires")

    # Metadata
    connected_at: datetime = Field(description="When user connected Gmail")
    last_sync: Optional[datetime] = Field(description="Last successful sync")
    status: GmailConnectionStatus = Field(default="active")


class GmailConnectionStatus(StrEnum):
    """Status of Gmail connection"""

    ACTIVE = "active"              # Working normally
    TOKEN_EXPIRED = "token_expired"  # Needs re-authentication
    REVOKED = "revoked"            # User revoked access
    ERROR = "error"                # Persistent errors
```

### Component Design

#### 1. OAuth Handler

```python
class GmailOAuthHandler:
    """Handles Gmail OAuth flow"""

    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

    def get_authorization_url(self, user_id: str, redirect_uri: str) -> str:
        """
        Generate OAuth URL for frontend redirect.

        Args:
            user_id: Internal user ID (passed as state)
            redirect_uri: Frontend callback URL

        Returns:
            Google OAuth authorization URL
        """
        flow = Flow.from_client_config(
            client_config=GOOGLE_CLIENT_CONFIG,
            scopes=self.SCOPES,
            redirect_uri=redirect_uri,
        )
        auth_url, _ = flow.authorization_url(
            access_type='offline',        # Get refresh_token
            include_granted_scopes='true',
            prompt='consent',             # Always show consent screen
            state=user_id,
        )
        return auth_url

    async def handle_callback(
        self,
        code: str,
        user_id: str,
        redirect_uri: str,
    ) -> GmailCredentials:
        """
        Exchange auth code for tokens and initialize Gmail watch.

        Args:
            code: Authorization code from Google
            user_id: Internal user ID
            redirect_uri: Must match the one used in authorization

        Returns:
            Stored Gmail credentials
        """
        # Exchange code for tokens
        flow = Flow.from_client_config(
            client_config=GOOGLE_CLIENT_CONFIG,
            scopes=self.SCOPES,
            redirect_uri=redirect_uri,
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Get user's Gmail address
        gmail_service = build('gmail', 'v1', credentials=credentials)
        profile = gmail_service.users().getProfile(userId='me').execute()

        # Setup inbox watch
        watch_response = gmail_service.users().watch(
            userId='me',
            body={
                'topicName': GMAIL_PUBSUB_TOPIC,
                'labelIds': ['INBOX'],
            }
        ).execute()

        # Store credentials
        gmail_creds = GmailCredentials(
            user_id=user_id,
            gmail_address=profile['emailAddress'],
            access_token=encrypt(credentials.token),
            refresh_token=encrypt(credentials.refresh_token),
            token_expiry=credentials.expiry,
            scopes=list(credentials.scopes),
            history_id=watch_response['historyId'],
            watch_expiry=datetime.fromtimestamp(
                int(watch_response['expiration']) / 1000
            ),
            connected_at=datetime.now(timezone.utc),
        )

        await self.credentials_store.save(gmail_creds)
        return gmail_creds
```

#### 2. Token Manager

```python
class GmailTokenManager:
    """Manages Gmail OAuth token lifecycle"""

    async def get_valid_credentials(self, user_id: str) -> Credentials:
        """
        Get valid credentials, refreshing if needed.

        Raises:
            TokenExpiredError: If refresh fails and re-auth needed
        """
        stored = await self.credentials_store.get(user_id)

        credentials = Credentials(
            token=decrypt(stored.access_token),
            refresh_token=decrypt(stored.refresh_token),
            token_uri='https://oauth2.googleapis.com/token',
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=stored.scopes,
        )

        if credentials.expired:
            try:
                credentials.refresh(Request())

                # Update stored credentials
                await self.credentials_store.update(
                    user_id=user_id,
                    access_token=encrypt(credentials.token),
                    token_expiry=credentials.expiry,
                )
            except RefreshError:
                # Refresh token invalid, user needs to re-authenticate
                await self.credentials_store.update(
                    user_id=user_id,
                    status=GmailConnectionStatus.TOKEN_EXPIRED,
                )
                raise TokenExpiredError(
                    "Gmail access expired. Please reconnect your account."
                )

        return credentials

    async def revoke_access(self, user_id: str) -> None:
        """Revoke Gmail access and clean up"""
        stored = await self.credentials_store.get(user_id)

        # Revoke token with Google
        requests.post(
            'https://oauth2.googleapis.com/revoke',
            params={'token': decrypt(stored.access_token)},
        )

        # Update status
        await self.credentials_store.update(
            user_id=user_id,
            status=GmailConnectionStatus.REVOKED,
        )
```

#### 3. Watch Renewal Service

```python
class GmailWatchRenewalService:
    """Renews Gmail watch() before expiration"""

    RENEWAL_BUFFER = timedelta(days=1)  # Renew 1 day before expiry

    async def check_and_renew_watches(self) -> None:
        """
        Scheduled job to renew expiring watches.
        Run daily via cron.
        """
        expiring_soon = await self.credentials_store.find_expiring_watches(
            before=datetime.now(timezone.utc) + self.RENEWAL_BUFFER
        )

        for creds in expiring_soon:
            try:
                await self.renew_watch(creds.user_id)
            except Exception as e:
                logger.error(
                    "watch_renewal_failed",
                    user_id=creds.user_id,
                    error=str(e),
                )

    async def renew_watch(self, user_id: str) -> None:
        """Renew Gmail watch for a user"""
        credentials = await self.token_manager.get_valid_credentials(user_id)
        gmail_service = build('gmail', 'v1', credentials=credentials)

        # Stop existing watch (optional, but clean)
        try:
            gmail_service.users().stop(userId='me').execute()
        except Exception:
            pass  # May not exist

        # Create new watch
        watch_response = gmail_service.users().watch(
            userId='me',
            body={
                'topicName': GMAIL_PUBSUB_TOPIC,
                'labelIds': ['INBOX'],
            }
        ).execute()

        # Update stored expiry
        await self.credentials_store.update(
            user_id=user_id,
            history_id=watch_response['historyId'],
            watch_expiry=datetime.fromtimestamp(
                int(watch_response['expiration']) / 1000
            ),
        )
```

### API Endpoints

```python
@router.get("/api/oauth/gmail/authorize")
async def get_gmail_auth_url(
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Get OAuth URL for frontend to redirect user"""
    auth_url = oauth_handler.get_authorization_url(
        user_id=user_id,
        redirect_uri=GMAIL_REDIRECT_URI,
    )
    return {"auth_url": auth_url}


@router.post("/api/oauth/gmail/callback")
async def gmail_oauth_callback(
    code: str,
    state: str,  # user_id
) -> dict:
    """Handle OAuth callback from frontend"""
    credentials = await oauth_handler.handle_callback(
        code=code,
        user_id=state,
        redirect_uri=GMAIL_REDIRECT_URI,
    )
    return {
        "status": "connected",
        "email": credentials.gmail_address,
    }


@router.post("/api/oauth/gmail/disconnect")
async def disconnect_gmail(
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Disconnect Gmail and revoke access"""
    await token_manager.revoke_access(user_id)
    return {"status": "disconnected"}


@router.get("/api/oauth/gmail/status")
async def gmail_connection_status(
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Check Gmail connection status"""
    creds = await credentials_store.get(user_id)
    if not creds:
        return {"connected": False}

    return {
        "connected": creds.status == GmailConnectionStatus.ACTIVE,
        "email": creds.gmail_address,
        "status": creds.status,
        "connected_at": creds.connected_at,
        "needs_reauth": creds.status == GmailConnectionStatus.TOKEN_EXPIRED,
    }
```

### User Onboarding Sequence

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           USER ONBOARDING JOURNEY                               │
└─────────────────────────────────────────────────────────────────────────────────┘

1. SIGN UP
   ┌─────────────────────────────────────┐
   │  Welcome to Trackable!              │
   │                                     │
   │  Track all your online orders       │
   │  in one place.                      │
   │                                     │
   │  [Sign up with Google]              │
   │  [Sign up with Email]               │
   └─────────────────────────────────────┘
                    │
                    ▼
2. CONNECT EMAIL (Core Value Prop)
   ┌─────────────────────────────────────┐
   │  Connect your email to auto-track   │
   │  orders                             │
   │                                     │
   │  We'll automatically detect orders  │
   │  from your inbox and track them     │
   │  for you.                           │
   │                                     │
   │  ✓ Only reads order-related emails  │
   │  ✓ We never store email content     │
   │  ✓ Disconnect anytime               │
   │                                     │
   │  [Connect Gmail]  [Skip for now]    │
   └─────────────────────────────────────┘
                    │
                    ▼
3. GOOGLE CONSENT SCREEN
   ┌─────────────────────────────────────┐
   │  ┌─────────────────────────────┐    │
   │  │ G  Sign in with Google      │    │
   │  └─────────────────────────────┘    │
   │                                     │
   │  Trackable wants to:                │
   │                                     │
   │  ☑ Read your email messages         │
   │                                     │
   │  [Allow]           [Cancel]         │
   └─────────────────────────────────────┘
                    │
                    ▼
4. SUCCESS + OPTIONAL BACKFILL
   ┌─────────────────────────────────────┐
   │  ✓ Gmail connected!                 │
   │                                     │
   │  Would you like us to find your     │
   │  recent orders?                     │
   │                                     │
   │  We can scan your last 30 days      │
   │  of emails to import existing       │
   │  orders.                            │
   │                                     │
   │  [Yes, find my orders]  [No thanks] │
   └─────────────────────────────────────┘
                    │
                    ▼
5. DASHBOARD (Ongoing)
   ┌─────────────────────────────────────┐
   │  Your Orders                        │
   │  ─────────────────────────────────  │
   │  📦 Nike - Air Max 90               │
   │     Out for delivery                │
   │     Return window: 12 days left     │
   │                                     │
   │  📦 Amazon - USB Cable              │
   │     Delivered yesterday             │
   │                                     │
   │  [+ Add order manually]             │
   └─────────────────────────────────────┘
```

### Initial Backfill (Optional)

After OAuth connection, optionally scan recent emails for existing orders:

```python
class OrderBackfillService:
    """Backfill orders from historical emails"""

    async def backfill_recent_orders(
        self,
        user_id: str,
        days: int = 30,
    ) -> BackfillResult:
        """
        Scan recent emails for order confirmations.

        Args:
            user_id: User to backfill for
            days: How far back to scan

        Returns:
            Summary of backfill results
        """
        credentials = await self.token_manager.get_valid_credentials(user_id)
        gmail_service = build('gmail', 'v1', credentials=credentials)

        # Search for order-related emails
        query = (
            f"newer_than:{days}d "
            "(subject:order OR subject:confirmation OR subject:shipped OR subject:delivery) "
            "-category:promotions"
        )

        results = gmail_service.users().messages().list(
            userId='me',
            q=query,
            maxResults=100,
        ).execute()

        orders_created = 0
        orders_skipped = 0

        for msg in results.get('messages', []):
            email = await self._fetch_email(gmail_service, msg['id'])

            if self.email_classifier.is_order_related(email):
                extracted = await self.input_processor.process(email)

                if extracted and not await self.is_duplicate(extracted, user_id):
                    await self.order_resolver.resolve(
                        extracted=extracted,
                        user_id=user_id,
                        source_type=SourceType.EMAIL,
                        source_id=msg['id'],
                    )
                    orders_created += 1
                else:
                    orders_skipped += 1

        return BackfillResult(
            emails_scanned=len(results.get('messages', [])),
            orders_created=orders_created,
            orders_skipped=orders_skipped,
        )
```

### Security Considerations

| Concern | Mitigation |
|---------|------------|
| **Token Storage** | Encrypt tokens at rest using AES-256; use cloud secret manager for encryption keys |
| **Token Transmission** | Always use HTTPS; tokens never sent to frontend |
| **Refresh Token Exposure** | Never log tokens; mask in error messages |
| **Scope Minimization** | Only request `gmail.readonly`, not full access |
| **User Revocation** | Honor revocation immediately; provide easy disconnect UI |
| **Token Refresh Failures** | Mark account as needing re-auth; notify user |

### Error Handling

```python
class OAuthError(Exception):
    """Base OAuth error"""
    pass

class TokenExpiredError(OAuthError):
    """Refresh token invalid, user must re-authenticate"""
    pass

class ScopeDeniedError(OAuthError):
    """User denied required scope"""
    pass

class RateLimitError(OAuthError):
    """Gmail API rate limit hit"""
    pass


# Error recovery strategies
ERROR_RECOVERY = {
    TokenExpiredError: "prompt_reauth",      # Show reconnect UI
    ScopeDeniedError: "explain_and_retry",   # Explain why scope needed
    RateLimitError: "exponential_backoff",   # Wait and retry
}
```

---

## Shared Components

### Data Store Interface

```python
class OrderStore:
    """Abstract interface for order persistence"""

    async def create(self, order: Order) -> Order:
        """Create new order"""

    async def update(self, order_id: str, updates: dict) -> Order:
        """Update existing order"""

    async def get(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""

    async def find_by_user(
        self,
        user_id: str,
        filters: Optional[OrderFilters] = None,
    ) -> list[Order]:
        """Find orders for user with optional filters"""

    async def find_by_merchant_order(
        self,
        user_id: str,
        merchant_name: str,
        order_number: str,
    ) -> Optional[Order]:
        """Find order by merchant + order number (for deduplication)"""
```

### Deduplication Strategy

```python
class OrderDeduplicator:
    """Prevents duplicate order creation from multiple email notifications"""

    async def is_duplicate(
        self,
        extracted: ExtractedOrderData,
        user_id: str,
    ) -> tuple[bool, Optional[Order]]:
        """
        Check if this is a duplicate based on:
        1. Exact order_number + merchant match
        2. Same items + total + date within 24h window
        3. Source_id already processed
        """

    async def should_update(
        self,
        existing: Order,
        new_data: ExtractedOrderData,
    ) -> bool:
        """Determine if new data warrants an update"""
```

### Error Handling

```python
class FlowErrorHandler:
    """Centralized error handling for both flows"""

    async def handle_extraction_failure(
        self,
        error: Exception,
        source: str,
        user_id: str,
    ) -> None:
        """Log extraction failure, optionally notify user"""

    async def handle_api_failure(
        self,
        error: Exception,
        service: str,
        retry_count: int,
    ) -> Optional[Any]:
        """Handle external API failures with retry logic"""

    async def handle_low_confidence(
        self,
        order: Order,
        user_id: str,
    ) -> None:
        """Handle low-confidence extractions needing review"""
```

---

## Implementation Plan

### Phase 1: Core Infrastructure

1. **Data Store Implementation**
   - Define storage backend (Firestore, PostgreSQL, etc.)
   - Implement OrderStore interface
   - Add order CRUD operations
   - Implement deduplication logic

2. **Enhanced Root Agent**
   - Update root_agent with proper instructions
   - Add order-related tools
   - Configure subagent routing

3. **Input Processor Integration**
   - Connect Gmail tools to input_processor
   - Add image processing capability
   - Implement `convert_extracted_to_order`

### Phase 2: Offline Flow

4. **Gmail Integration**
   - Set up Gmail API OAuth flow
   - Implement watch() for push notifications
   - Configure Pub/Sub topic and subscription

5. **Email Watcher Service**
   - Implement notification handler
   - Add email fetching logic
   - Build email classifier

6. **Order Resolver**
   - Implement create/update logic
   - Add merge strategy for updates
   - Handle edge cases (split shipments, etc.)

### Phase 3: Real-time Flow

7. **Chat Context Management**
   - Implement ChatContext class
   - Add conversation state tracking
   - Build proactive deadline mentions

8. **Additional Subagents**
   - Implement tracking_agent
   - Implement return_agent
   - Implement policy_agent

9. **User Preferences**
   - Notification settings integration
   - Timezone handling
   - Reminder sensitivity

### Phase 4: Interventions

10. **Intervention Engine**
    - Deadline monitoring
    - Notification scheduling
    - Multi-channel delivery (email, push, SMS)

11. **Proactive Features**
    - Return window reminders
    - Delivery confirmations
    - Refund tracking alerts

---

## Configuration

### Environment Variables

```bash
# Gmail API
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GMAIL_WATCH_TOPIC=projects/{project}/topics/gmail-notifications

# Pub/Sub
PUBSUB_SUBSCRIPTION=projects/{project}/subscriptions/gmail-push

# Data Store
DATABASE_URL=
REDIS_URL=  # For caching/rate limiting

# Agent
GOOGLE_GENAI_API_KEY=  # For Gemini
DEFAULT_MODEL=gemini-2.5-flash

# Notifications
SENDGRID_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
```

### Feature Flags

```python
FEATURES = {
    "offline_flow_enabled": True,
    "realtime_flow_enabled": True,
    "push_notifications": True,
    "sms_notifications": False,
    "image_processing": True,
    "proactive_interventions": True,
    "low_confidence_review": True,
}
```

---

## Metrics and Monitoring

### Key Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Email Processing Latency | Time from email receipt to order created | < 30s |
| Extraction Accuracy | % of orders correctly extracted | > 95% |
| Chat Response Time | Time to first response in real-time flow | < 2s |
| Intervention Delivery Rate | % of scheduled interventions delivered | > 99% |
| User Clarification Rate | % of orders needing human review | < 10% |

### Logging

```python
# Structured logging for observability
logger.info(
    "order_created",
    extra={
        "user_id": user_id,
        "order_id": order.id,
        "source_type": source_type,
        "confidence": order.confidence_score,
        "flow": "offline",  # or "realtime"
    }
)
```

---

## Security Considerations

1. **OAuth Token Management**: Secure storage and refresh of Gmail tokens
2. **Data Encryption**: Encrypt PII at rest and in transit
3. **Rate Limiting**: Prevent abuse of real-time chat
4. **Input Validation**: Sanitize all user inputs and extracted data
5. **Audit Logging**: Track all order modifications

---

## Future Enhancements

1. **Multi-provider Email Support**: Outlook, Yahoo, etc.
2. **Browser Extension**: Capture orders from any website
3. **Merchant API Integration**: Direct order import from Amazon, etc.
4. **ML-based Classification**: Improve email classification accuracy
5. **Voice Interface**: Alexa/Google Assistant integration
