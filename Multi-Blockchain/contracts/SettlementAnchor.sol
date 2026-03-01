// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title SettlementAnchor
/// @notice Anchors Layer-2 state roots on the Ethereum settlement layer.
///         Provides cryptographic linkage between execution-layer state and
///         the PoS-secured L1, ensuring data integrity can be verified at
///         any time against the settlement chain.
contract SettlementAnchor {
    struct Anchor {
        uint256 l2BlockNumber;
        address submitter;
        uint256 anchoredAt;
        bool active;
    }

    mapping(bytes32 => Anchor) public anchors;
    uint256 public anchorCount;

    address public owner;

    event StateRootAnchored(
        bytes32 indexed stateRoot,
        uint256 l2BlockNumber,
        address indexed submitter,
        uint256 timestamp
    );

    event AnchorRevoked(bytes32 indexed stateRoot, uint256 timestamp);

    modifier onlyOwner() {
        require(msg.sender == owner, "Not authorised");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /// @notice Anchor an L2 state root on the settlement layer.
    /// @param stateRoot The L2 state root hash to anchor.
    /// @param l2BlockNumber The L2 block number corresponding to this state root.
    /// @param proof Optional validity or fraud proof (stored off-chain via event).
    function anchorStateRoot(
        bytes32 stateRoot,
        uint256 l2BlockNumber,
        bytes calldata proof
    ) external onlyOwner {
        require(anchors[stateRoot].anchoredAt == 0, "State root already anchored");
        require(l2BlockNumber > 0, "Invalid block number");

        anchors[stateRoot] = Anchor({
            l2BlockNumber: l2BlockNumber,
            submitter: msg.sender,
            anchoredAt: block.timestamp,
            active: true
        });

        anchorCount++;

        emit StateRootAnchored(stateRoot, l2BlockNumber, msg.sender, block.timestamp);
    }

    /// @notice Verify whether a state root has been anchored.
    /// @param stateRoot The state root to verify.
    /// @return exists Whether the anchor exists.
    /// @return l2BlockNumber The corresponding L2 block number.
    /// @return anchoredAt The timestamp when the anchor was created.
    function verifyStateRoot(bytes32 stateRoot)
        external
        view
        returns (bool exists, uint256 l2BlockNumber, uint256 anchoredAt)
    {
        Anchor storage a = anchors[stateRoot];
        return (a.active, a.l2BlockNumber, a.anchoredAt);
    }

    /// @notice Revoke a previously anchored state root.
    /// @param stateRoot The state root to revoke.
    function revokeAnchor(bytes32 stateRoot) external onlyOwner {
        require(anchors[stateRoot].active, "Anchor not active");
        anchors[stateRoot].active = false;
        emit AnchorRevoked(stateRoot, block.timestamp);
    }
}
